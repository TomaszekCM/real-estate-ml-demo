from django.contrib import admin
from .models import ValuationRequest, ValuationResult


@admin.register(ValuationRequest)
class ValuationRequestAdmin(admin.ModelAdmin):
    list_display = ['city', 'district', 'area_sqm', 'rooms', 'created_at']
    list_filter = ['city', 'created_at']
    search_fields = ['city', 'district']
    readonly_fields = ['created_at']


@admin.register(ValuationResult)
class ValuationResultAdmin(admin.ModelAdmin):
    list_display = ['get_city', 'estimated_price', 'price_per_sqm', 'model_version', 'created_at']
    list_filter = ['model_version', 'created_at']
    readonly_fields = ['created_at']
    
    def get_city(self, obj):
        return f"{obj.request.city} ({obj.request.area_sqm}m²)"
    get_city.short_description = 'Property'
