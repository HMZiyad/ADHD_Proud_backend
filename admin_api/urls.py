from django.urls import path
from .views import (
    AdminProfileView,
    DashboardStatsView,
    DashboardChartView,
    DashboardTransactionsView,
    AdminOrderListView,
    AdminOrderUpdateView,
    AdminProductCreateView,
    AdminProductDetailView,
    AdminCustomerListView,
    AdminCustomerDetailView,
    AdminNotificationListView,
    AdminNotificationMarkReadView,
    AdminBlogCategoryListView,
    AdminBlogPostListCreateView,
    AdminBlogPostDetailView,
)

urlpatterns = [
    # Profile
    path('profile/', AdminProfileView.as_view(), name='admin-profile'),

    # Dashboard
    path('dashboard/stats/', DashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('dashboard/chart/', DashboardChartView.as_view(), name='admin-dashboard-chart'),
    path('dashboard/transactions/', DashboardTransactionsView.as_view(), name='admin-dashboard-transactions'),

    # Orders
    path('orders/', AdminOrderListView.as_view(), name='admin-orders-list'),
    path('orders/<str:order_number>/', AdminOrderUpdateView.as_view(), name='admin-orders-update'),

    # Products
    path('products/', AdminProductCreateView.as_view(), name='admin-products-create'),
    path('products/<int:pk>/', AdminProductDetailView.as_view(), name='admin-products-detail'),

    # Customers
    path('customers/', AdminCustomerListView.as_view(), name='admin-customers-list'),
    path('customers/<int:pk>/', AdminCustomerDetailView.as_view(), name='admin-customers-detail'),

    # Notifications
    path('notifications/', AdminNotificationListView.as_view(), name='admin-notifications-list'),
    path('notifications/mark-read/', AdminNotificationMarkReadView.as_view(), name='admin-notifications-mark-read'),

    # Blog
    path('blog/categories/', AdminBlogCategoryListView.as_view(), name='admin-blog-categories'),
    path('blog/', AdminBlogPostListCreateView.as_view(), name='admin-blog-list-create'),
    path('blog/<int:pk>/', AdminBlogPostDetailView.as_view(), name='admin-blog-detail'),
]
