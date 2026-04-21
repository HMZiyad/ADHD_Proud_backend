from django.urls import path
from .views import (
    ProfileMeView, ProfileStatsView,
    SavedAddressListCreateView, SavedAddressDetailView,
    WishlistListCreateView, WishlistItemDeleteView,
    CartView, CartItemCreateView, CartItemDetailView
)

urlpatterns = [
    path('me/', ProfileMeView.as_view(), name='profile-me'),
    path('me/stats/', ProfileStatsView.as_view(), name='profile-stats'),
    path('addresses/', SavedAddressListCreateView.as_view(), name='address-list'),
    path('addresses/<int:pk>/', SavedAddressDetailView.as_view(), name='address-detail'),
    path('wishlist/', WishlistListCreateView.as_view(), name='wishlist-list'),
    path('wishlist/<int:pk>/', WishlistItemDeleteView.as_view(), name='wishlist-delete'),
    
    path('cart/', CartView.as_view(), name='cart-detail'),
    path('cart/items/', CartItemCreateView.as_view(), name='cart-items-add'),
    path('cart/items/<int:pk>/', CartItemDetailView.as_view(), name='cart-items-detail'),
]
