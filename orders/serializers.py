from rest_framework import serializers
from .models import Order, OrderItem, TrackingEvent


class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ['id', 'label', 'location', 'timestamp']


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_name', 'product_image', 'size', 'color', 'quantity', 'price']


class OrderListSerializer(serializers.ModelSerializer):
    """Compact view for Order History listing."""
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'payment_status', 'tracking_number',
            'total_price', 'estimated_delivery', 'created_at', 'items',
        ]


class OrderDetailSerializer(OrderListSerializer):
    """Full order detail including tracking event timeline."""
    tracking_events = TrackingEventSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + [
            'tracking_events',
            'shipping_first_name', 'shipping_last_name', 'shipping_email',
            'shipping_phone', 'shipping_address', 'shipping_city',
            'shipping_state', 'shipping_zip', 'shipping_country', 'order_notes',
        ]


class TrackOrderSerializer(serializers.Serializer):
    """For the Track Order search endpoint."""
    tracking_number = serializers.CharField(required=True)


# --------------------------------------------------------------------------
# Checkout / Payment serializers
# --------------------------------------------------------------------------

class CheckoutItemSerializer(serializers.Serializer):
    """A single cart line item sent from the frontend."""
    product_id = serializers.IntegerField()
    size = serializers.CharField(required=False, allow_blank=True, default='')
    color = serializers.CharField(required=False, allow_blank=True, default='')
    quantity = serializers.IntegerField(min_value=1, default=1)


class CreateCheckoutSessionSerializer(serializers.Serializer):
    """Full checkout payload from the frontend. Items are read from the DB cart."""
    # Shipping / billing info
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    zip_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    order_notes = serializers.CharField(required=False, allow_blank=True, default='')

