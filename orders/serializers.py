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
            'id', 'order_number', 'status', 'tracking_number',
            'total_price', 'estimated_delivery', 'created_at', 'items'
        ]


class OrderDetailSerializer(OrderListSerializer):
    """Full order detail including tracking event timeline."""
    tracking_events = TrackingEventSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ['tracking_events']


class TrackOrderSerializer(serializers.Serializer):
    """For the Track Order search endpoint."""
    tracking_number = serializers.CharField(required=True)
