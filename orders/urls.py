from django.urls import path
from .views import (
    OrderListView,
    OrderDetailView,
    TrackOrderView,
    CreateCheckoutSessionView,
    StripeWebhookView,
)

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
    path('track/', TrackOrderView.as_view(), name='order-track'),
    # Stripe payment endpoints
    path('checkout/create-session/', CreateCheckoutSessionView.as_view(), name='create-checkout-session'),
    path('webhook/', StripeWebhookView.as_view(), name='stripe-webhook'),
    # Keep this last — it catches <order_number> patterns
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
]
