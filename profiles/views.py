from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import UserProfile, SavedAddress, Wishlist, Cart, CartItem
from .serializers import (
    UserProfileSerializer, ProfileStatsSerializer,
    SavedAddressSerializer, WishlistSerializer,
    CartSerializer, CartItemSerializer
)


class ProfileMeView(generics.RetrieveUpdateAPIView):
    """GET/PUT the authenticated user's profile."""
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class ProfileStatsView(APIView):
    """Returns aggregated counts for the profile header stats widget."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        stats = {
            'total_orders': user.orders.count(),
            'wishlist_count': user.wishlist.count(),
            'saved_addresses_count': user.addresses.count(),
        }
        serializer = ProfileStatsSerializer(stats)
        return Response(serializer.data)


class SavedAddressListCreateView(generics.ListCreateAPIView):
    """List all or create a new saved address."""
    serializer_class = SavedAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedAddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update or delete a specific saved address."""
    serializer_class = SavedAddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return SavedAddress.objects.filter(user=self.request.user)


class WishlistListCreateView(generics.ListCreateAPIView):
    """List wishlist or add a product to it."""
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WishlistItemDeleteView(generics.DestroyAPIView):
    """Remove a product from the wishlist."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

class CartView(generics.RetrieveUpdateAPIView):
    """Retrieve or apply promo code to the user's cart."""
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return cart

class CartItemCreateView(generics.CreateAPIView):
    """Add a new item to cart."""
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

class CartItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Update quantity or delete an item in the cart."""
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)
