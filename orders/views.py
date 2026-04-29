import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .models import Order, OrderItem
from .serializers import (
    OrderListSerializer,
    OrderDetailSerializer,
    TrackOrderSerializer,
    CreateCheckoutSessionSerializer,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


# ---------------------------------------------------------------------------
# Existing order views
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Stripe Payment views
# ---------------------------------------------------------------------------

class CreateCheckoutSessionView(APIView):
    """
    POST /api/orders/checkout/create-session/

    1. Validates the cart payload
    2. Looks up each product in the DB (price snapshot)
    3. Creates a pending Order + OrderItems in the database
    4. Creates a Stripe Checkout Session
    5. Returns { session_url, order_number } to the frontend
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from profiles.models import Cart

        serializer = CreateCheckoutSessionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data

        try:
            cart = Cart.objects.prefetch_related('items__product').get(user=request.user)
        except Cart.DoesNotExist:
            return Response({'error': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        if not cart.items.exists():
            return Response({'error': 'Cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── 1. Resolve products and build line items ───────────────────────
        line_items = []
        order_items_to_create = []

        for item in cart.items.all():
            product = item.product
            unit_price = product.price
            qty = item.quantity

            # Stripe expects amount in smallest currency unit (cents)
            line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': product.name,
                        'description': f"Size: {item.size} | Color: {item.color}" if item.size or item.color else product.name,
                    },
                    'unit_amount': int(unit_price * 100),
                },
                'quantity': qty,
            })

            primary_image = product.images.filter(is_primary=True).first()
            if not primary_image:
                primary_image = product.images.first()
            
            image_url = request.build_absolute_uri(primary_image.image.url) if primary_image else ''

            order_items_to_create.append({
                'product': product,
                'product_name': product.name,
                'product_image': image_url,
                'size': item.size,
                'color': item.color,
                'quantity': qty,
                'price': unit_price,
            })

        # Add Shipping line item
        if cart.shipping > 0:
             line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Shipping',
                    },
                    'unit_amount': int(cart.shipping * 100),
                },
                'quantity': 1,
            })

        # Add Tax line item
        if cart.tax > 0:
             line_items.append({
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Tax',
                    },
                    'unit_amount': int(cart.tax * 100),
                },
                'quantity': 1,
            })

        # ── 2. Create the pending Order in the DB ──────────────────────────
        order = Order.objects.create(
            user=request.user,
            total_price=cart.total,
            payment_status='pending',
            status='pending',
            shipping_first_name=data['first_name'],
            shipping_last_name=data['last_name'],
            shipping_email=data['email'],
            shipping_phone=data.get('phone', ''),
            shipping_address=data['address'],
            shipping_city=data['city'],
            shipping_state=data.get('state', ''),
            shipping_zip=data.get('zip_code', ''),
            shipping_country=data.get('country', ''),
            order_notes=data.get('order_notes', ''),
        )

        for oi in order_items_to_create:
            OrderItem.objects.create(order=order, **oi)

        # ── 3. Create Stripe Checkout Session ──────────────────────────────
        frontend_url = settings.FRONTEND_URL.rstrip('/')

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=line_items,
                mode='payment',
                customer_email=data['email'],
                success_url=f"{frontend_url}/order-success?order={order.order_number}&session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{frontend_url}/cart?order={order.order_number}&cancelled=true",
                metadata={
                    'order_number': order.order_number,
                    'user_id': str(request.user.id),
                },
            )
        except stripe.error.StripeError as e:
            # Roll back the pending order if Stripe fails
            order.delete()
            return Response({'error': str(e.user_message)}, status=status.HTTP_502_BAD_GATEWAY)

        # ── 4. Save the session ID for webhook matching ────────────────────
        order.stripe_session_id = session.id
        order.save(update_fields=['stripe_session_id'])

        # ── 5. Clear the user's cart ───────────────────────────────────────
        cart.items.all().delete()

        return Response({
            'session_url': session.url,
            'session_id': session.id,
            'order_number': order.order_number,
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    """
    POST /api/orders/webhook/

    Stripe calls this endpoint after a payment event.
    - Verifies the request signature using STRIPE_WEBHOOK_SECRET
    - On `checkout.session.completed` → marks the order as paid
    - On `checkout.session.expired`  → marks the order payment as failed
    """
    permission_classes = [AllowAny]  # Stripe signs the payload; no JWT needed
    authentication_classes = []      # Skip JWT authentication

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        # ── Verify Stripe signature ────────────────────────────────────────
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            # Invalid payload
            return HttpResponse('Invalid payload', status=400)
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return HttpResponse('Invalid signature', status=400)

        event_type = event['type']
        session = event['data']['object']
        order_number = session.get('metadata', {}).get('order_number')

        if not order_number:
            # Event not tied to one of our orders — ignore
            return HttpResponse('OK', status=200)

        # ── Handle checkout.session.completed ─────────────────────────────
        if event_type == 'checkout.session.completed':
            try:
                order = Order.objects.get(order_number=order_number)
            except Order.DoesNotExist:
                return HttpResponse('Order not found', status=404)

            order.payment_status = 'paid'
            order.status = 'processing'   # move to processing once paid
            order.stripe_session_id = session.get('id', order.stripe_session_id)
            order.save(update_fields=['payment_status', 'status', 'stripe_session_id'])

            # ── 4. Deduct Inventory Stock ──────────────────────────────────
            from shop.models import ProductSize
            for item in order.items.all():
                if item.product:
                    if item.size:
                        try:
                            size_obj = ProductSize.objects.get(product=item.product, size=item.size)
                            size_obj.stock = max(0, size_obj.stock - item.quantity)
                            size_obj.save() # This also triggers product.update_total_stock() via model override
                        except ProductSize.DoesNotExist:
                            # Fallback to global stock
                            item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
                            item.product.save()
                    else:
                        # Global stock deduction
                        item.product.stock_quantity = max(0, item.product.stock_quantity - item.quantity)
                        item.product.save()

        # ── Handle checkout.session.expired ───────────────────────────────
        elif event_type == 'checkout.session.expired':
            try:
                order = Order.objects.get(order_number=order_number)
                order.payment_status = 'failed'
                order.save(update_fields=['payment_status'])
            except Order.DoesNotExist:
                pass

        # Always return 200 so Stripe doesn't keep retrying
        return HttpResponse('OK', status=200)

