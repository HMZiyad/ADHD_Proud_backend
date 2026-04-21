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
    list_display = ('order_number', 'user', 'status', 'total_price', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'tracking_number', 'user__email')
    readonly_fields = ('order_number', 'created_at')
    inlines = [OrderItemInline, TrackingEventInline]


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ('order', 'label', 'location', 'timestamp')
