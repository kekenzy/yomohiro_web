from django.contrib import admin
from .models import Location, TimeSlot, Reservation, Plan, MemberProfile, PaymentTransaction

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'capacity', 'price_per_30min', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['start_time', 'end_time', 'is_active']
    list_filter = ['is_active']
    ordering = ['start_time']

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['customer_name', 'location', 'date', 'time_slot', 'status', 'created_at']
    list_filter = ['status', 'date', 'location', 'time_slot']
    search_fields = ['customer_name', 'customer_email', 'customer_phone']
    ordering = ['-date', 'time_slot__start_time']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('予約情報', {
            'fields': ('location', 'time_slot', 'date', 'status')
        }),
        ('お客様情報', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('その他', {
            'fields': ('notes', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'is_default', 'is_active', 'created_at']
    list_filter = ['is_active', 'is_default']
    search_fields = ['name', 'description']
    ordering = ['price']

@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'user', 'gender', 'plan', 'created_at']
    list_filter = ['gender', 'plan', 'created_at']
    search_fields = ['full_name', 'user__username', 'user__email', 'phone']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'amount', 'status', 'square_payment_id', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['square_payment_id', 'square_order_id', 'payment_link_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']
