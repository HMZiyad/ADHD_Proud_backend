from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Max
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.pagination import PageNumberPagination

from profiles.models import UserProfile
from orders.models import Order
from shop.models import Product

from .serializers import (
    AdminProfileSerializer,
    DashboardStatsSerializer,
    OrdersChartSerializer,
    RecentTransactionSerializer,
    AdminOrderSerializer,
    AdminProductSerializer,
    AdminCustomerSerializer,
    AdminNotificationSerializer,
    AdminBlogPostSerializer,
    AdminBlogCategorySerializer,
)

User = get_user_model()

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class StandardResultsPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------------------------------------------------------------------------
# 1. Admin Profile  GET/PATCH /api/admin/profile/
# ---------------------------------------------------------------------------

class AdminProfileView(APIView):
    """
    GET  /api/admin/profile/  — return the admin's profile
    PATCH /api/admin/profile/ — update name, phone, avatar
    """
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_or_create_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile

    def get(self, request):
        profile = self._get_or_create_profile(request.user)
        serializer = AdminProfileSerializer(profile, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        profile = self._get_or_create_profile(request.user)
        serializer = AdminProfileSerializer(
            profile, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 2. Dashboard Stats  GET /api/admin/dashboard/stats/
# ---------------------------------------------------------------------------

class DashboardStatsView(APIView):
    """GET /api/admin/dashboard/stats/"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_orders = Order.objects.count()
        total_products = Product.objects.count()
        total_customers = User.objects.filter(is_staff=False).count()
        total_revenue = Order.objects.filter(
            payment_status='paid'
        ).aggregate(rev=Sum('total_price'))['rev'] or 0

        data = {
            'total_orders': total_orders,
            'total_products': total_products,
            'total_customers': total_customers,
            'total_revenue': total_revenue,
        }
        serializer = DashboardStatsSerializer(data)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 3. Orders Chart  GET /api/admin/dashboard/chart/
# ---------------------------------------------------------------------------

DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


class DashboardChartView(APIView):
    """
    GET /api/admin/dashboard/chart/?period=week
    Returns order counts grouped by day for the past 7 days.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        start = today - timedelta(days=6)

        # Build a map of date -> count from the DB
        qs = (
            Order.objects
            .filter(created_at__date__gte=start)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(orders=Count('id'))
        )
        db_map = {row['day']: row['orders'] for row in qs}

        # Fill every day in the range (even if 0 orders)
        result = []
        for i in range(7):
            day = start + timedelta(days=i)
            label = DAY_LABELS[day.weekday()]
            result.append({'date': label, 'orders': db_map.get(day, 0)})

        serializer = OrdersChartSerializer(result, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 4. Recent Transactions  GET /api/admin/dashboard/transactions/
# ---------------------------------------------------------------------------

class DashboardTransactionsView(APIView):
    """GET /api/admin/dashboard/transactions/?limit=5"""
    permission_classes = [IsAdminUser]

    PAYMENT_STATUS_MAP = {
        'paid': 'Completed',
        'pending': 'Pending',
        'failed': 'Failed',
    }

    def get(self, request):
        limit = int(request.query_params.get('limit', 5))
        orders = (
            Order.objects
            .select_related('user', 'user__profile')
            .order_by('-created_at')[:limit]
        )

        result = []
        for order in orders:
            profile = getattr(order.user, 'profile', None)
            name = profile.full_name if profile and profile.full_name else order.user.email
            result.append({
                'id': f'TX-{order.order_number}',
                'user': name,
                'amount': order.total_price,
                'status': self.PAYMENT_STATUS_MAP.get(order.payment_status, 'Pending'),
                'date': order.created_at,
            })

        serializer = RecentTransactionSerializer(result, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 5. Admin Orders  GET /api/admin/orders/  PATCH /api/admin/orders/{order_number}/
# ---------------------------------------------------------------------------

class AdminOrderListView(generics.ListAPIView):
    """
    GET /api/admin/orders/
    Query params: ?page=1&page_size=10&status=Pending
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminOrderSerializer
    pagination_class = StandardResultsPagination

    REVERSE_STATUS_MAP = {
        'Pending': 'pending',
        'Processing': 'processing',
        'Shipped': 'in_transit',
        'Delivered': 'delivered',
        'Cancelled': 'cancelled',
    }

    def get_queryset(self):
        qs = Order.objects.select_related('user', 'user__profile').prefetch_related('items')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            db_status = self.REVERSE_STATUS_MAP.get(status_filter, status_filter.lower())
            qs = qs.filter(status=db_status)
        return qs.order_by('-created_at')


class AdminOrderUpdateView(APIView):
    """PATCH /api/admin/orders/{order_number}/"""
    permission_classes = [IsAdminUser]

    ALLOWED_TRANSITIONS = {
        'Shipped': 'in_transit',
        'Delivered': 'delivered',
        'Cancelled': 'cancelled',
        # Also accept the internal names directly
        'in_transit': 'in_transit',
        'delivered': 'delivered',
        'cancelled': 'cancelled',
        'processing': 'processing',
        'pending': 'pending',
    }

    def patch(self, request, order_number):
        try:
            order = Order.objects.select_related('user', 'user__profile').prefetch_related('items').get(
                order_number=order_number
            )
        except Order.DoesNotExist:
            return Response({'error': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status', '').strip()
        if not new_status:
            return Response({'error': '"status" field is required.'}, status=status.HTTP_400_BAD_REQUEST)

        db_status = self.ALLOWED_TRANSITIONS.get(new_status)
        if db_status is None:
            return Response(
                {'error': f'Invalid status "{new_status}". Allowed: Shipped, Delivered, Cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = db_status
        order.save(update_fields=['status'])

        serializer = AdminOrderSerializer(order, context={'request': request})
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 6. Admin Products  POST /api/admin/products/
#                    PATCH/DELETE /api/admin/products/{id}/
# ---------------------------------------------------------------------------

class AdminProductCreateView(APIView):
    """
    GET  /api/admin/products/
    POST /api/admin/products/
    """
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        products = Product.objects.prefetch_related('images', 'sizes').order_by('-created_at')
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(products, request)
        if page is not None:
            serializer = AdminProductSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        serializer = AdminProductSerializer(products, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminProductSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        # Re-serialize for consistent response
        out = AdminProductSerializer(product, context={'request': request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class AdminProductDetailView(APIView):
    """
    PATCH  /api/admin/products/{id}/
    DELETE /api/admin/products/{id}/
    """
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_product(self, pk):
        try:
            return Product.objects.prefetch_related('images', 'sizes').get(pk=pk)
        except Product.DoesNotExist:
            return None

    def patch(self, request, pk):
        product = self._get_product(pk)
        if not product:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminProductSerializer(
            product, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        out = AdminProductSerializer(updated, context={'request': request})
        return Response(out.data)

    def delete(self, request, pk):
        product = self._get_product(pk)
        if not product:
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 7. Admin Customers  GET /api/admin/customers/
#                     PATCH/DELETE /api/admin/customers/{id}/
# ---------------------------------------------------------------------------

class AdminCustomerListView(generics.ListAPIView):
    """GET /api/admin/customers/"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminCustomerSerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        return (
            User.objects
            .filter(is_staff=False)
            .select_related('profile')
            .prefetch_related('orders')
            .annotate(
                total_orders=Count('orders'),
                total_spent=Sum('orders__total_price'),
                last_order_date=Max('orders__created_at__date'),
            )
            .order_by('-date_joined')
        )


class AdminCustomerDetailView(APIView):
    """
    PATCH  /api/admin/customers/{id}/
    DELETE /api/admin/customers/{id}/
    """
    permission_classes = [IsAdminUser]

    def _get_user(self, pk):
        try:
            return (
                User.objects
                .filter(is_staff=False)
                .select_related('profile')
                .prefetch_related('orders')
                .annotate(
                    total_orders=Count('orders'),
                    total_spent=Sum('orders__total_price'),
                    last_order_date=Max('orders__created_at__date'),
                )
                .get(pk=pk)
            )
        except User.DoesNotExist:
            return None

    def patch(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Update User fields
        email = request.data.get('email')
        if email:
            user.email = email
            user.save(update_fields=['email'])

        # Update Profile fields
        profile, _ = UserProfile.objects.get_or_create(user=user)
        name = request.data.get('name')
        phone = request.data.get('phone')
        if name:
            profile.full_name = name
        if phone:
            profile.phone = phone
        profile.save()

        # Re-fetch to pick up fresh annotations
        user = self._get_user(pk)
        serializer = AdminCustomerSerializer(user)
        return Response(serializer.data)

    def delete(self, request, pk):
        user = self._get_user(pk)
        if not user:
            return Response({'error': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# 8. Notifications  GET /api/admin/notifications/ 
#                   POST /api/admin/notifications/mark-read/
# ---------------------------------------------------------------------------

from .models import AdminNotification

class AdminNotificationListView(generics.ListAPIView):
    """GET /api/admin/notifications/"""
    permission_classes = [IsAdminUser]
    serializer_class = AdminNotificationSerializer

    def get_queryset(self):
        return AdminNotification.objects.all()[:50]


class AdminNotificationMarkReadView(APIView):
    """POST /api/admin/notifications/mark-read/"""
    permission_classes = [IsAdminUser]

    def post(self, request):
        AdminNotification.objects.filter(unread=True).update(unread=False)
        return Response({"success": True})


# ---------------------------------------------------------------------------
# 9. Admin Blog  GET/POST /api/admin/blog/
#                GET/PATCH/DELETE /api/admin/blog/{id}/
#                GET /api/admin/blog/categories/
# ---------------------------------------------------------------------------

from blog.models import Post as BlogPost, Category as BlogCategory


class AdminBlogCategoryListView(generics.ListAPIView):
    """GET /api/admin/blog/categories/ — for populating the category dropdown."""
    permission_classes = [IsAdminUser]
    serializer_class = AdminBlogCategorySerializer
    queryset = BlogCategory.objects.all().order_by('name')
    pagination_class = None  # return all, no pagination


class AdminBlogPostListCreateView(APIView):
    """
    GET  /api/admin/blog/          — paginated list of all posts
    POST /api/admin/blog/          — create a new post (multipart)
    """
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        posts = BlogPost.objects.select_related('author', 'author__profile', 'category').order_by('-created_at')
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(posts, request)
        if page is not None:
            serializer = AdminBlogPostSerializer(page, many=True, context={'request': request})
            return paginator.get_paginated_response(serializer.data)
        serializer = AdminBlogPostSerializer(posts, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = AdminBlogPostSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        post = serializer.save()
        out = AdminBlogPostSerializer(post, context={'request': request})
        return Response(out.data, status=status.HTTP_201_CREATED)


class AdminBlogPostDetailView(APIView):
    """
    GET    /api/admin/blog/{id}/   — retrieve a single post
    PATCH  /api/admin/blog/{id}/   — partial update
    DELETE /api/admin/blog/{id}/   — delete
    """
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _get_post(self, pk):
        try:
            return BlogPost.objects.select_related('author', 'author__profile', 'category').get(pk=pk)
        except BlogPost.DoesNotExist:
            return None

    def get(self, request, pk):
        post = self._get_post(pk)
        if not post:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminBlogPostSerializer(post, context={'request': request})
        return Response(serializer.data)

    def patch(self, request, pk):
        post = self._get_post(pk)
        if not post:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AdminBlogPostSerializer(
            post, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        out = AdminBlogPostSerializer(updated, context={'request': request})
        return Response(out.data)

    def delete(self, request, pk):
        post = self._get_post(pk)
        if not post:
            return Response({'error': 'Post not found.'}, status=status.HTTP_404_NOT_FOUND)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
