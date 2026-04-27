from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.timesince import timesince
from django.utils.text import slugify

from profiles.models import UserProfile
from orders.models import Order, OrderItem
from shop.models import Product, ProductImage, ProductSize, Category as ShopCategory
from blog.models import Post as BlogPost, Category as BlogCategory

User = get_user_model()


# ---------------------------------------------------------------------------
# Admin Profile
# ---------------------------------------------------------------------------

class AdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for GET/PATCH /api/admin/profile/"""
    id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'full_name', 'email', 'phone', 'avatar']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if data.get('avatar') and request:
            # Make avatar URL absolute if it's a relative path
            avatar = data['avatar']
            if avatar and not avatar.startswith('http'):
                data['avatar'] = request.build_absolute_uri(avatar)
        return data


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardStatsSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    total_products = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_revenue = serializers.FloatField()


class OrdersChartSerializer(serializers.Serializer):
    date = serializers.CharField()
    orders = serializers.IntegerField()


class RecentTransactionSerializer(serializers.Serializer):
    id = serializers.CharField()
    user = serializers.CharField()
    amount = serializers.FloatField()
    status = serializers.CharField()
    date = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# Admin Orders
# ---------------------------------------------------------------------------

class AdminOrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='product_name')
    image = serializers.CharField(source='product_image')
    qty = serializers.IntegerField(source='quantity')

    class Meta:
        model = OrderItem
        fields = ['name', 'image', 'size', 'color', 'qty', 'price']


class AdminOrderSerializer(serializers.ModelSerializer):
    customer = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at', format='%Y-%m-%d', read_only=True)
    total = serializers.FloatField(source='total_price', read_only=True)
    status = serializers.SerializerMethodField()
    items = AdminOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer', 'date', 'total', 'status', 'tracking_number', 'items']

    def get_customer(self, obj):
        profile = getattr(obj.user, 'profile', None)
        if profile and profile.full_name:
            return profile.full_name
        return obj.user.email

    def get_status(self, obj):
        """Return title-cased status that matches frontend expectations."""
        STATUS_MAP = {
            'pending': 'Pending',
            'processing': 'Processing',
            'in_transit': 'Shipped',
            'delivered': 'Delivered',
            'cancelled': 'Cancelled',
        }
        return STATUS_MAP.get(obj.status, obj.status.title())


# ---------------------------------------------------------------------------
# Admin Products
# ---------------------------------------------------------------------------

class AdminProductVariantSerializer(serializers.Serializer):
    size = serializers.CharField()
    stock = serializers.IntegerField(default=0)


class AdminProductSerializer(serializers.ModelSerializer):
    """Used for Create / Update / read responses."""
    category = serializers.SerializerMethodField()
    inventory = serializers.IntegerField(source='stock_quantity', read_only=True)
    image = serializers.SerializerMethodField()
    variants = serializers.SerializerMethodField()

    # Write-only inputs
    category_slug = serializers.SlugField(write_only=True, required=False)
    stock = serializers.IntegerField(write_only=True, required=False, default=0)
    sizes = serializers.CharField(
        write_only=True, required=False, allow_blank=True, default='',
        help_text="Comma-separated sizes: S,M,L,XL"
    )
    image_file = serializers.ImageField(
        write_only=True, required=False, source='image', allow_null=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'category', 'price', 'inventory', 'image', 'variants',
            # write-only
            'category_slug', 'stock', 'sizes', 'image_file',
        ]

    def get_category(self, obj):
        return obj.category.name if obj.category else None

    def get_image(self, obj):
        request = self.context.get('request')
        primary = obj.images.filter(is_primary=True).first() or obj.images.first()
        if primary:
            url = primary.image.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_variants(self, obj):
        return [{'size': s.size, 'stock': 0} for s in obj.sizes.all()]

    def create(self, validated_data):
        category_slug = validated_data.pop('category_slug', None)
        stock = validated_data.pop('stock', 0)
        sizes_str = validated_data.pop('sizes', '')
        image_file = validated_data.pop('image', None)

        # Resolve category
        category = None
        if category_slug:
            try:
                category = ShopCategory.objects.get(slug=category_slug)
            except ShopCategory.DoesNotExist:
                pass

        # Auto-generate slug from name
        from django.utils.text import slugify
        import uuid
        name = validated_data.get('name', '')
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        product = Product.objects.create(
            category=category,
            slug=slug,
            stock_quantity=stock,
            description=validated_data.pop('description', ''),
            **validated_data,
        )

        # Create primary image
        if image_file:
            ProductImage.objects.create(product=product, image=image_file, is_primary=True)

        # Create size variants
        if sizes_str:
            for size in [s.strip() for s in sizes_str.split(',') if s.strip()]:
                ProductSize.objects.create(product=product, size=size)

        return product

    def update(self, instance, validated_data):
        category_slug = validated_data.pop('category_slug', None)
        stock = validated_data.pop('stock', None)
        sizes_str = validated_data.pop('sizes', None)
        image_file = validated_data.pop('image', None)

        if category_slug:
            try:
                instance.category = ShopCategory.objects.get(slug=category_slug)
            except ShopCategory.DoesNotExist:
                pass

        if stock is not None:
            instance.stock_quantity = stock

        if image_file:
            # Replace the primary image
            instance.images.filter(is_primary=True).delete()
            ProductImage.objects.create(product=instance, image=image_file, is_primary=True)

        if sizes_str is not None:
            instance.sizes.all().delete()
            for size in [s.strip() for s in sizes_str.split(',') if s.strip()]:
                ProductSize.objects.create(product=instance, size=size)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ---------------------------------------------------------------------------
# Admin Customers
# ---------------------------------------------------------------------------

class AdminCustomerOrderSerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(source='created_at', format='%Y-%m-%d', read_only=True)
    total = serializers.FloatField(source='total_price', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'date', 'total', 'status']

    def get_status(self, obj):
        STATUS_MAP = {
            'pending': 'Pending',
            'processing': 'Processing',
            'in_transit': 'Shipped',
            'delivered': 'Delivered',
            'cancelled': 'Cancelled',
        }
        return STATUS_MAP.get(obj.status, obj.status.title())


class AdminCustomerSerializer(serializers.ModelSerializer):
    """Serializer for admin customer list & detail."""
    name = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    joined = serializers.DateTimeField(source='date_joined', format='%Y-%m-%d', read_only=True)
    total_orders = serializers.IntegerField(read_only=True)
    total_spent = serializers.FloatField(read_only=True)
    last_order_date = serializers.DateField(read_only=True)
    order_history = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'phone', 'status',
            'joined', 'total_orders', 'total_spent', 'last_order_date',
            'order_history',
        ]

    def get_name(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.full_name if profile and profile.full_name else obj.email

    def get_phone(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.phone if profile else ''

    def get_status(self, obj):
        return 'Active' if obj.is_active else 'Inactive'

    def get_order_history(self, obj):
        orders = obj.orders.order_by('-created_at')[:10]
        return AdminCustomerOrderSerializer(orders, many=True).data


# ---------------------------------------------------------------------------
# Admin Notifications
# ---------------------------------------------------------------------------

from .models import AdminNotification

class AdminNotificationSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = AdminNotification
        fields = ['id', 'title', 'body', 'type', 'unread', 'time']

    def get_time(self, obj):
        return f"{timesince(obj.created_at)} ago"


# ---------------------------------------------------------------------------
# Admin Blog
# ---------------------------------------------------------------------------

class AdminBlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ['id', 'name', 'slug']


class AdminBlogPostSerializer(serializers.ModelSerializer):
    """Used for Create / Update / Read of blog posts."""
    category = AdminBlogCategorySerializer(read_only=True)
    author_name = serializers.SerializerMethodField()
    image = serializers.ImageField(required=False, allow_null=True)

    # Write-only
    category_slug = serializers.SlugField(write_only=True, required=False)

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'category', 'author_name', 'image',
            'excerpt', 'content', 'published_date', 'created_at',
            # write-only
            'category_slug',
        ]
        read_only_fields = ['id', 'slug', 'author_name', 'created_at']

    def get_author_name(self, obj):
        profile = getattr(obj.author, 'profile', None)
        if profile and profile.full_name:
            return profile.full_name
        return obj.author.email

    def _resolve_category(self, category_slug):
        if not category_slug:
            return None
        try:
            return BlogCategory.objects.get(slug=category_slug)
        except BlogCategory.DoesNotExist:
            return None

    def _unique_slug(self, title, exclude_pk=None):
        base = slugify(title)
        slug = base
        counter = 1
        qs = BlogPost.objects.all()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        while qs.filter(slug=slug).exists():
            slug = f"{base}-{counter}"
            counter += 1
        return slug

    def create(self, validated_data):
        category_slug = validated_data.pop('category_slug', None)
        validated_data['category'] = self._resolve_category(category_slug)
        validated_data['slug'] = self._unique_slug(validated_data.get('title', ''))
        validated_data['author'] = self.context['request'].user
        return BlogPost.objects.create(**validated_data)

    def update(self, instance, validated_data):
        category_slug = validated_data.pop('category_slug', None)
        if category_slug is not None:
            instance.category = self._resolve_category(category_slug)
        if 'title' in validated_data and validated_data['title'] != instance.title:
            instance.slug = self._unique_slug(validated_data['title'], exclude_pk=instance.pk)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
