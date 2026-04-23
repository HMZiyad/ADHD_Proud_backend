from django.contrib import admin
from .models import Order, OrderItem, TrackingEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product_image', 'size', 'color', 'quantity', 'price')


class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 1


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'status', 'payment_status', 'total_price', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('order_number', 'tracking_number', 'user__email', 'stripe_session_id')
    readonly_fields = ('order_number', 'stripe_session_id', 'created_at')
    fieldsets = (
        ('Order Info', {
            'fields': ('order_number', 'user', 'status', 'tracking_number', 'total_price', 'estimated_delivery', 'created_at'),
        }),
        ('Payment', {
            'fields': ('payment_status', 'stripe_session_id'),
        }),
        ('Shipping Address', {
            'fields': (
                'shipping_first_name', 'shipping_last_name', 'shipping_email', 'shipping_phone',
                'shipping_address', 'shipping_city', 'shipping_state', 'shipping_zip', 'shipping_country',
                'order_notes',
            ),
        }),
    )
    inlines = [OrderItemInline, TrackingEventInline]


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ('order', 'label', 'location', 'timestamp')

