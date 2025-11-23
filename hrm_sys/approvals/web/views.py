from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.db.models import Q
from django.views.decorators.http import require_http_methods,require_POST
from django.contrib import messages
from approvals.forms import ApprovalCreateForm
from approvals.models import ApprovalType, ApprovalFlow, ApprovalRecord, ApprovalAttachment
from django.contrib.auth.decorators import login_required
from users.models import Employee
from django.core.files.storage import default_storage
from datetime import datetime

@require_http_methods(["GET", "POST"])
def create_approval(request):
    """
    Create approval record, assign to first approver from selected list.
    """
    if request.method == "POST":
        form = ApprovalCreateForm(request.POST, request.FILES)
        if form.is_valid():
            approval_type = form.cleaned_data["approval_type"]
            approvers = form.cleaned_data["approvers"]
            rich_content = form.cleaned_data["rich_content"]
            
            print(approvers)

            # Assign to first approver
            first_approver = approvers.first() if approvers.exists() else None
            employee = Employee.objects.get(employee_code=request.user.username)  #request.user.username
            
            if not first_approver:
                return HttpResponse(
                    "<div class='text-red-500'>Please select at least one approver.</div>"
                )

            # Create approval record
            record = ApprovalRecord.objects.create(
                approval_type=approval_type,
                creator=employee,  # use request.user
                approver=first_approver,
                level=1,
                status="pending",
                rich_content=rich_content,
                is_proper_approver=True,
                
            )

            # Save attachments
            for f in request.FILES.getlist("attachments"):
                print(f.name)
                if not record.attachments.filter(file=f.name).exists():
                    ApprovalAttachment.objects.create(
                        approval=record,
                        file=f,
                        uploadedby=employee
                    )

            return HttpResponse(
                "<div class='text-green-600'>Approval submitted and assigned to first approver.</div>"
            )
        else:
            errors_html = "".join([
                f"<p class='text-red-500'>{field}: {error}</p>"
                for field, error_list in form.errors.items()
                for error in error_list
            ])
            return HttpResponse(errors_html)
    else:
        form = ApprovalCreateForm()
    return render(request, "approvals/create_approval.html", {"form": form})


@require_http_methods(["GET"])
def load_approvers(request):
    """
    HTMX endpoint: returns options for approvers based on selected approval type
    and the logged-in user's department/subdepartment.
    """
    approval_type_id = request.GET.get("approval_type")
    user_employee_code = "EMP-DA654E" #request.user.username  # same as employee code

    try:
        employee = Employee.objects.get(employee_code=user_employee_code)
    except Employee.DoesNotExist:
        return HttpResponse("<option value=''>No employee record found</option>")

    approvers_qs = ApprovalFlow.objects.filter(
        approval_type_id=approval_type_id,
        is_active=True
    ).order_by("level")

    # Filter approvers by same department/subdepartment
    approvers = []
    for flow in approvers_qs:
        if flow.approver:
            if (flow.department is None or flow.department == employee.department) and \
               (flow.sub_department is None or flow.sub_department == employee.sub_department):
                approvers.append(flow.approver)

    if not approvers:
        return HttpResponse("<option value=''>No approvers available</option>")

    options_html = "".join([f"<option value='{a.id}'>{a.full_name} ({a.employee_code})</option>" for a in approvers])
    return HttpResponse(options_html)


def my_pending_approvals(request):
    employee_code = request.user.username  # Assuming username == employee_code

    try:
        employee = Employee.objects.get(employee_code=employee_code)
    except Employee.DoesNotExist:
        return render(request, "approvals/pending_approvals.html", {"approvals": []})

    # Get all pending approvals
    pending_approvals = ApprovalRecord.objects.filter(
        status="pending"
    ).select_related("creator", "approval_type")

    my_approvals = []

    for approval in pending_approvals:
        # Get the flow for this approval type
        flows = ApprovalFlow.objects.filter(
            approval_type=approval.approval_type,
            is_active=True
        ).order_by("level")

        # Determine current level for this approval
        current_level = approval.level or 1

        # Find the flow record for current level
        current_flow = flows.filter(level=current_level).first()

        if current_flow:
            # Check if current employee is the approver for this level
            dept_match = (current_flow.department is None or current_flow.department == employee.department)
            sub_dept_match = (current_flow.sub_department is None or current_flow.sub_department == employee.sub_department)

            if current_flow.approver == employee and dept_match and sub_dept_match:
                my_approvals.append(approval)

    # Order by created date descending
    my_approvals = sorted(my_approvals, key=lambda x: x.created_at, reverse=True)

    return render(request, "approvals/pending_approvals.html", {"approvals": my_approvals})



def approve_action(request, record_id):
    """
    Handles Approve/Reject action for a pending approval.
    Saves optional comment and returns an inline message (HTMX).
    """
    if request.method != "POST":
        return HttpResponse("<div class='text-red-500'>Invalid request method.</div>")

    action = request.POST.get("action")
    comment = request.POST.get("comment", "").strip()  # Get optional comment
    record = get_object_or_404(ApprovalRecord, id=record_id)
    
    employee_code = request.user.username
    try:
        current_employee = Employee.objects.get(employee_code=employee_code)
    except Employee.DoesNotExist:
        return HttpResponse("<div class='text-red-500'>Employee record not found.</div>")

    # Ensure current user is the assigned approver
    if record.approver != current_employee:
        return HttpResponse("<div class='text-red-500'>You are not the assigned approver for this record.</div>")

    # Save comment if provided
    if comment:
        if record.comment:
            record.comment += f"\n{current_employee.full_name}: {comment}"
        else:
            record.comment = f"{current_employee.full_name}: {comment}"

    if action == "approve":
        next_flow = ApprovalFlow.objects.filter(
            approval_type=record.approval_type,
            level=record.level + 1,
            is_active=True,
            
        ).first()
        
        record.approved_at = datetime.now()

        if next_flow:
            # Assign to next approver
            record.approver = next_flow.approver
            record.level += 1
            record.is_proper_approver = True
            record.save()
            return HttpResponse(f"<div class='text-green-600'>Approval advanced to {next_flow.approver.full_name}.</div>")
        else:
            # Final approval
            record.status = "approved"
            record.save()
            return HttpResponse("<div class='text-green-600'>Approval fully approved.</div>")

    elif action == "reject":
        record.status = "rejected"
        record.approved_at = datetime.now()
        record.save()
        return HttpResponse("<div class='text-red-600'>Approval rejected.</div>")

    else:
        return HttpResponse("<div class='text-red-500'>Invalid action.</div>")


def approval_detail(request, approval_id):
    employee_code = request.user.username
    employee = Employee.objects.get(employee_code=employee_code)

    approval = get_object_or_404(
        ApprovalRecord.objects.select_related("creator", "approval_type", "approver"),
        pk=approval_id
    )

    # Get all steps for this approval type in order
    steps = ApprovalFlow.objects.filter(
        approval_type=approval.approval_type
    ).order_by("level").select_related("approver")

    # Prepare a list of steps with status and comments
    step_data = []
    for step in steps:
        record = ApprovalRecord.objects.filter(
            approval_type=approval.approval_type,
            creator=approval.creator,
            level=step.level
        ).first()
        step_data.append({
            "level": step.level,
            "approver": step.approver,
            "status": record.status if record else "pending",
            "comment": record.comment if record and record.comment else "",
        })

    is_current_approver = approval.approver == employee and approval.status == "pending"
  

    return render(request, "approvals/approval_detail.html", {
        "approval": approval,
        "steps": step_data,
        "is_current_approver": is_current_approver,
       
    })
    

def my_created_approvals(request):
    """
    Renders the My Created Approvals page.
    The initial page load shows all approvals; search/filter is handled separately.
    """
    user = Employee.objects.get(employee_code=request.user.username)

    # Get all approvals for this user
    approvals = ApprovalRecord.objects.filter(creator=user).select_related(
        "approval_type", "approver", "creator"
    ).prefetch_related("approval_type__flows").order_by("-created_at")[:5]
    
 

    # Build timeline data
    items = build_approval_timeline(approvals)


    return render(request, "approvals/my_created_approvals.html", {
        "items": items,
    })



def search_my_created_approvals(request: HttpRequest):
    """
    Returns filtered approval records based on search query or status.
    Works with HTMX partial swap.
    """
    user = Employee.objects.get(employee_code=request.user.username)

    status_filter = request.GET.get("filter", "all")
    search_query = request.GET.get("search", "").strip()

    approvals = ApprovalRecord.objects.filter(creator=user).select_related(
        "approval_type", "approver", "creator"
    ).prefetch_related("approval_type__flows").order_by("-created_at")

    # Apply status filter
    if status_filter == "approved":
        approvals = approvals.filter(status="approved")
    elif status_filter == "pending":
        approvals = approvals.filter(status="pending")

    # Apply search
    if search_query:
        approvals = approvals.filter(
            Q(approval_type__name__icontains=search_query) |
            Q(rich_content__icontains=search_query)
        )

    # Build timeline data
    items = build_approval_timeline(approvals)
    
  

    # Return HTMX partial
    return render(request, "approvals/partials/my_created_approvals_list.html", {
        "items": items,
        "search_query": search_query,
        "filter": status_filter,
    })

def build_approval_timeline(approval_records):
    """
    Builds a timeline for approval stages based on their level.
    Each stage is marked as:
        - approved: stage < current level OR approved at this level
        - pending: current level not yet approved
        - upcoming: future levels
    """
    timeline_items = []

    for approval in approval_records:
        flows = approval.approval_type.flows.filter(is_active=True).order_by("level")
        stages = []

        for flow in flows:
            # Check if a record exists for this object and this level
            record = ApprovalRecord.objects.filter(
                approval_type=approval.approval_type,
                content_type=approval.content_type,
                object_id=approval.object_id,
                level=flow.level
            ).first()

            # Determine status based on level
            if record:
                if record.status == "approved":
                    status = "approved"
                    approved_at = record.approved_at
                else:
                    # Not yet approved
                    if flow.level < approval.level:
                        status = "approved"
                        approved_at = record.approved_at
                    elif flow.level == approval.level:
                        status = record.status  # usually pending
                        approved_at = record.approved_at
                    else:
                        status = "upcoming"
                        approved_at = None
            else:
                # No record exists yet
                if flow.level < approval.level:
                    status = "approved"
                    approved_at = None
                elif flow.level == approval.level:
                    status = "pending"
                    approved_at = None
                else:
                    status = "upcoming"
                    approved_at = None

            stages.append({
                "flow": flow,
                "record": record,
                "status": status,
                "approved_at": approved_at,
            })

        # Last approval datetime
        approved_records = [s for s in stages if s["status"] == "approved" and s["approved_at"]]
        last_approval_date = max([s["approved_at"] for s in approved_records], default=None)

        timeline_items.append({
            "approval": approval,
            "stages": stages,
            "last_approval_date": last_approval_date,
        })

    return timeline_items


@login_required
def edit_approval(request, approval_id):
    # Get the approval record
    approval = get_object_or_404(ApprovalRecord, id=approval_id)
    employee = Employee.objects.get(employee_code=request.user.username)
    
 

    form = ApprovalCreateForm(instance=approval)
    
    records = ApprovalRecord.objects.filter(
    content_type=approval.content_type,
    object_id=approval.object_id
    ).order_by("level", "id")   # ensure stable order

    unique_levels = {}
    for r in records:
        if r.level not in unique_levels:  # first record for this level only
            unique_levels[r.level] = r

    stages = list(unique_levels.values())
    # queryset
    initial_files = ApprovalAttachment.objects.filter(approval=approval)
    
 

    # -------------------------
    # CHECK EDITABILITY
    # -------------------------
    # Editable only if current level is 1
    editable = approval.level == 1

    # -------------------------
    # POST REQUEST
    # -------------------------
    if request.method == "POST":
        if not editable:
            html = """
            <div class='bg-red-100 text-red-700 px-4 py-3 rounded-lg mb-4 text-sm'>
                You cannot edit this approval because it has progressed beyond level 1.
            </div>
            """
            return HttpResponse(html)
        
        # Update comment/description
        approval.comment = request.POST.get("comment", "").strip()
        approval.save()
        
        remove_ids = request.POST.getlist("remove_files")
        print("Removing attachments:", remove_ids)
        if remove_ids:
            ApprovalAttachment.objects.filter(id__in=remove_ids).delete()

        # Handle attachments
        files = request.FILES.getlist("new_files")
        print(files)
        for f in files:
            if not approval.attachments.filter(file=f.name).exists():
                ApprovalAttachment.objects.create(
                    approval=approval,
                    file=f,
                    uploadedby=employee,
                )

        # HTMX success response
        html = """
        <div class="bg-green-100 text-green-700 px-4 py-3 rounded-lg mb-4 text-sm">
            Approval updated successfully!
        </div>
        """
        return HttpResponse(html)

    # -------------------------
    # GET REQUEST → Load page
    # -------------------------
    context = {
        "approval": approval,
        "editable": editable,
        "stages": stages,
        "initial_files": initial_files,
        "form": form,
    }
    return render(request, "approvals/edit_approval.html", context)






