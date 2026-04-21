from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Order
from .serializers import OrderListSerializer, OrderDetailSerializer, TrackOrderSerializer


class OrderListView(generics.ListAPIView):
    """Order History: list all orders for the authenticated user."""
    serializer_class = OrderListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'tracking_events')


class OrderDetailView(generics.RetrieveAPIView):
    """Single order details with full tracking timeline."""
    serializer_class = OrderDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'order_number'

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items', 'tracking_events')


class TrackOrderView(APIView):
    """Track an order by its tracking number."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tracking_number = request.query_params.get('tracking_number', '').strip()
        if not tracking_number:
            return Response({'error': 'tracking_number query parameter is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.prefetch_related('items', 'tracking_events').get(
                user=request.user,
                tracking_number=tracking_number
            )
        except Order.DoesNotExist:
            return Response({'error': 'No order found with this tracking number.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderDetailSerializer(order, context={'request': request})
        return Response(serializer.data)
