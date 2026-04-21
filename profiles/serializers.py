from rest_framework import serializers
from .models import UserProfile, SavedAddress, Wishlist, Cart, CartItem
from shop.serializers import ProductListSerializer


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    member_since = serializers.DateTimeField(source='user.date_joined', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'email', 'full_name', 'avatar', 'phone', 'city', 'member_since']
        read_only_fields = ['id', 'email', 'member_since']


class ProfileStatsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    wishlist_count = serializers.IntegerField()
    saved_addresses_count = serializers.IntegerField()


class SavedAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedAddress
        fields = [
            'id', 'label', 'full_name', 'street_address', 'apt_suite',
            'city', 'state', 'zip_code', 'country', 'phone', 'is_default'
        ]
        read_only_fields = ['id']

    def _get_profile_name(self):
        """Retrieve the authenticated user's full_name from their UserProfile."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            return request.user.profile.full_name
        except UserProfile.DoesNotExist:
            return None

    def validate_full_name(self, value):
        """
        Enforce that the address full_name matches the UserProfile full_name.
        If the profile name is not set yet, allow any name (first-time setup).
        """
        profile_name = self._get_profile_name()
        if profile_name and value and value.strip() != profile_name.strip():
            raise serializers.ValidationError(
                f"Name must match your account name '{profile_name}'. "
                f"Update your profile name first if you want to use a different name."
            )
        return value

    def validate(self, attrs):
        """Auto-fill full_name from UserProfile if not provided."""
        if not attrs.get('full_name'):
            profile_name = self._get_profile_name()
            if profile_name:
                attrs['full_name'] = profile_name
            else:
                raise serializers.ValidationError(
                    {"full_name": "Please set your full name in your profile before adding an address."}
                )
        return attrs


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Wishlist
        fields = ['id', 'product', 'product_id', 'added_at']
        read_only_fields = ['id', 'added_at']

    def validate_product_id(self, value):
        from shop.models import Product
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError("Product not found.")
        return value

    def create(self, validated_data):
        product_id = validated_data.pop('product_id')
        from shop.models import Product
        product = Product.objects.get(id=product_id)
        return Wishlist.objects.create(product=product, **validated_data)


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    total_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'size', 'color', 'quantity', 'total_price', 'added_at']
        read_only_fields = ['id', 'added_at', 'total_price']

    def validate_product_id(self, value):
        from shop.models import Product
        if not Product.objects.filter(id=value).exists():
            raise serializers.ValidationError("Product not found.")
        return value

    def create(self, validated_data):
        from .models import Cart
        cart, _ = Cart.objects.get_or_create(user=self.context['request'].user)
        product_id = validated_data.pop('product_id')
        size = validated_data.get('size', '')
        color = validated_data.get('color', '')
        quantity = validated_data.get('quantity', 1)
        
        from shop.models import Product
        product = Product.objects.get(id=product_id)

        # Check if item with exact size/color already exists in cart, if so, just increment quantity
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, 
            product=product, 
            size=size, 
            color=color,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
            
        return cart_item

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    subtotal = serializers.FloatField(read_only=True)
    shipping = serializers.FloatField(read_only=True)
    tax = serializers.FloatField(read_only=True)
    total = serializers.FloatField(read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'promo_code', 'items', 'subtotal', 'shipping', 'tax', 'total']
