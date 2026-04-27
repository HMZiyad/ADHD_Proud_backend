from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    ForgotPasswordSerializer,
    VerifyOTPSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
)
from .models import OTPVerification
from .tasks import send_otp_email_task

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)

class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ForgotPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            otp = OTPVerification.generate_otp(user)
            send_otp_email_task.delay(user.email, otp.code)
        except User.DoesNotExist:
            # Silently pass to avoid email enumeration
            pass
            
        return Response({
            "message": "If an account exists, a 5-digit verification code has been sent."
        }, status=status.HTTP_200_OK)

class VerifyOTPView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = VerifyOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']
        
        try:
            user = User.objects.get(email=email)
            otp = OTPVerification.objects.filter(
                user=user, 
                code=code, 
                is_verified=False
            ).latest('created_at')
            
            # Check expiration (e.g. 15 minutes)
            if timezone.now() > otp.created_at + timedelta(minutes=15):
                return Response({"error": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)
                
            otp.is_verified = True
            otp.save()
            return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, OTPVerification.DoesNotExist):
            return Response({"error": "Invalid code or email."}, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(generics.GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = ResetPasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(email=email)
            # Find a recently verified OTP (e.g. within last 30 minutes)
            otp = OTPVerification.objects.filter(
                user=user, 
                is_verified=True,
                created_at__gte=timezone.now() - timedelta(minutes=30)
            ).latest('created_at')
            
            user.set_password(new_password)
            user.save()
            
            # Invalidate all OTPs to prevent reuse
            OTPVerification.objects.filter(user=user).delete()
            
            return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)
            
        except (User.DoesNotExist, OTPVerification.DoesNotExist):
            return Response({"error": "User not found or OTP not verified. Please verify your email first."}, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(generics.GenericAPIView):
    """POST /api/users/change-password/ — for logged-in users."""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        if not user.check_password(current_password):
            return Response(
                {"error": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
