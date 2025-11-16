# approvals/forms.py
from django import forms
from .models import ApprovalRecord
from users.models import Employee
from tinymce.widgets import TinyMCE

class ApprovalCreateForm(forms.ModelForm):
    approvers = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.all(),
        widget=forms.SelectMultiple(attrs={"class": "approver-select"})
    )

    class Meta:
        model = ApprovalRecord
        fields = ["approval_type", "rich_content", "approvers"]
        widgets = {
            "rich_content": TinyMCE(attrs={'cols': 80, 'rows': 30}),
        }
        labels = {
            "rich_content": "Approval Details",
            "document_attachments": "Attach Documents",
        }