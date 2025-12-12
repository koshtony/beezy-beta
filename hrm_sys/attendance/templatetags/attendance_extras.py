from django import template
from django.utils import timezone


register = template.Library()

@register.filter
def count_true(queryset, field_name):
    """
    Count how many items in queryset have field_name == True.
    Usage: {{ attendances|count_true:"is_late_check_in" }}
    """
    if not queryset:
        return 0
    return queryset.filter(**{field_name: True}).count()

@register.filter
def current_month(queryset):
    """
    Filter a queryset to only include records from the current month.
    Usage: {{ attendances|current_month }}
    """
    if not queryset:
        return queryset.none()
    now = timezone.now()
    return queryset.filter(check_in_date__year=now.year,
                           check_in_date__month=now.month)
