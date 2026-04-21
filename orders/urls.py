from django.urls import path
from .views import OrderListView, OrderDetailView, TrackOrderView

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
    path('track/', TrackOrderView.as_view(), name='order-track'),
    path('<str:order_number>/', OrderDetailView.as_view(), name='order-detail'),
]
