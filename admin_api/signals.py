from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .models import AdminNotification

@receiver(post_save, sender=Order)
def create_order_notification(sender, instance, created, **kwargs):
    if created:
        profile = getattr(instance.user, 'profile', None)
        name = profile.full_name if profile and profile.full_name else instance.user.email
        
        AdminNotification.objects.create(
            title="New Order Placed",
            body=f"{name} placed an order for ${instance.total_price}",
            type="order"
        )
