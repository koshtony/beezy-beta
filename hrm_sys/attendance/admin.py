from django.contrib import admin
from .models import Station

@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = (
        "name", 
        "address", 
        "latitude", 
        "longitude", 
        "location_pin", 
        "updated_by", 
        "last_updated"
    )
    search_fields = ("name", "address")
    readonly_fields = ("last_updated",)
