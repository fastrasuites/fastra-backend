from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, AllowAny

from django.core.mail import send_mail
from django.utils.text import slugify
from django.conf import settings
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context

from users.models import TenantUser

from .models import Tenant, Domain, TenantCreationOTP, GlobalUser
from .serializers import TenantCreationSerializer, OTPVerificationSerializer, TenantAccessSerializer
from .permissions import IsSuperUserOrTenantAdmin
# from .serializers import TenantRegistrationSerializer
from .utils import Util


# class TenantRegistrationViewSet(viewsets.ViewSet):
#     serializer_class = TenantRegistrationSerializer
#     permission_classes = [AllowAny]
#
#     @transaction.atomic
#     def create(self, request):
#         try:
#             serializer = TenantRegistrationSerializer(data=request.data)
#             if serializer.is_valid(raise_exception=True):
#                 # Create tenant and user
#                 tenant = serializer.save()
#
#                 # Set up domain
#                 api_base_domain = settings.API_BASE_DOMAIN
#                 sanitized_name = slugify(tenant.schema_name, allow_unicode=True)
#
#                 domain = Domain.objects.create(
#                     domain=f"{sanitized_name}.{api_base_domain}",
#                     tenant=tenant,
#                     is_primary=True
#                 )
#
#                 # Retrieve the user (now associated with the tenant)
#                 user = tenant.user
#
#                 # Additional tenant-specific setup
#                 with tenant_context(tenant):
#                     pass
#
#                 # Generate and send verification email
#                 token = RefreshToken.for_user(user)
#                 token['email'] = user.email
#                 token['tenant'] = tenant.schema_name
#                 verification_url = f'https://{domain.domain}/email-verify?token={str(token.access_token)}'
#
#                 email_body = f'Hi {tenant.company_name},\n\nUse the link below to verify your email:\n{verification_url}'
#                 email_data = {
#                     'email_body': email_body,
#                     'to_email': user.email,
#                     'email_subject': 'Verify Your Email'
#                 }
#                 Util.send_email(email_data)
#
#                 return Response({
#                     'detail': 'Tenant created successfully. Please confirm your email address.',
#                     'tenant_url': f"https://{domain.domain}"
#                 }, status=status.HTTP_201_CREATED)
#
#         except Exception as e:
#             transaction.set_rollback(True)
#             return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST


class TenantCreationViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = TenantCreationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Check or create OTP entry
        otp_entry, created = TenantCreationOTP.objects.get_or_create(email=email)
        if not created and otp_entry.is_expired():
            otp_entry.delete()
            otp_entry = TenantCreationOTP.objects.create(email=email)

        # Generate OTP and send email
        otp_entry.generate_otp()
        send_mail(
            "Your OTP for Tenant Creation",
            f"Your OTP is {otp_entry.otp}. It expires in 10 minutes.",
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )
        return Response({"detail": "OTP sent to your email."}, status=status.HTTP_201_CREATED)


class OTPVerificationViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp_input = serializer.validated_data["otp"]

        try:
            otp_entry = TenantCreationOTP.objects.get(email=email, is_verified=False)
        except TenantCreationOTP.DoesNotExist:
            return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate OTP
        if otp_entry.is_expired() or otp_entry.otp != otp_input:
            return Response({"error": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        otp_entry.is_verified = True
        otp_entry.save()

        return Response({"detail": "OTP verified successfully."}, status=status.HTTP_200_OK)

class TenantFinalizationViewSet(viewsets.ViewSet):
    def create(self, request):
        serializer = TenantCreationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        company_name = serializer.validated_data["company_name"]
        schema_name = serializer.validated_data["schema_name"]

        try:
            otp_entry = TenantCreationOTP.objects.get(email=email, is_verified=True)
        except TenantCreationOTP.DoesNotExist:
            return Response({"error": "OTP verification required."}, status=status.HTTP_400_BAD_REQUEST)

        # Finalize tenant creation
        tenant = Tenant.objects.create(schema_name=schema_name, company_name=company_name)
        Domain.objects.create(tenant=tenant, domain=f"{schema_name}.fastrasuite.com", is_primary=True)

        # Clean up OTP entry
        otp_entry.delete()

        return Response({"detail": "Tenant created successfully."}, status=status.HTTP_201_CREATED)



class TenantAccessViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsSuperUserOrTenantAdmin]

    def create(self, request):
        serializer = TenantAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        global_user_id = serializer.validated_data['global_user_id']
        tenant_id = serializer.validated_data['tenant_id']
        role = serializer.validated_data['role']

        # Ensure user exists
        try:
            global_user = GlobalUser.objects.get(id=global_user_id)
            tenant = Tenant.objects.get(id=tenant_id)
        except (GlobalUser.DoesNotExist, Tenant.DoesNotExist):
            return Response({"error": "User or Tenant not found."}, status=status.HTTP_404_NOT_FOUND)

        # Assign user to tenant with role
        tenant_user, created = TenantUser.objects.update_or_create(
            global_user=global_user,
            tenant=tenant,
            defaults={'role': role}
        )

        message = "User assigned to tenant." if created else "User role updated in tenant."
        return Response({"message": message}, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        try:
            tenant_user = TenantUser.objects.get(id=pk)
            tenant_user.delete()
            return Response({"message": "User access removed from tenant."}, status=status.HTTP_204_NO_CONTENT)
        except TenantUser.DoesNotExist:
            return Response({"error": "User access not found."}, status=status.HTTP_404_NOT_FOUND)
