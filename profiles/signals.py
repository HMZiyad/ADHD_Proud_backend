from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import UserProfile, Cart

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create a UserProfile and Cart whenever a new User is saved."""
    if created:
        UserProfile.objects.create(user=instance)
        Cart.objects.create(user=instance)
