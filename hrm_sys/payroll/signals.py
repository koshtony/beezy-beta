from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from approvals.models import ApprovalRecord
from payroll.models import EmployeePayroll


@receiver(post_save, sender=ApprovalRecord)
def sync_payroll_with_approval(sender, instance, **kwargs):
    if instance.approval_type.name != "Payroll":
        return

    content_type = ContentType.objects.get_for_model(EmployeePayroll)

    if instance.content_type != content_type:
        return

    payroll = EmployeePayroll.objects.get(id=instance.object_id)

    if instance.is_fully_approved:
        payroll.mark_approved()
    elif instance.is_rejected:
        payroll.mark_rejected()
