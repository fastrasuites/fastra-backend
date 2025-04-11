import jwt
from urllib.parse import urlparse

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import login as auth_login
from django.contrib.sites.shortcuts import get_current_site
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.db import transaction, connection

from django_tenants.utils import schema_context, tenant_context

from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.errors.exceptions import TenantNotFoundException, InvalidCredentialsException
from registration.utils import check_otp_time_expired, compare_password, set_tenant_schema, generate_tokens
from registration.models import Tenant, Domain
from users.models import TenantUser

from .models import CompanyProfile, OTP
from .serializers import TenantSerializer, VerifyEmailSerializer, RequestForgottenPasswordSerializer, \
    ForgottenPasswordSerializer, CompanyProfileSerializer, ResendVerificationEmailSerializer
from .utils import Util
from .permissions import IsAdminUser


class VerifyEmail(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyEmailSerializer

    @csrf_exempt
    def get(self, request):
        otp_token = request.GET.get('token')
        current_site = get_current_site(request).domain

        if not otp_token:
            return Response({'error': 'No Token provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Extract tenant subdomain/schema name from the request's current site domain
        tenant_subdomain = current_site.split('.')[0]

        try:
            # Find tenant based on the extracted subdomain
            tenant = Tenant.objects.get(schema_name=tenant_subdomain)

            if tenant.is_verified:
                return Response({'status': 'already_verified', 'message': 'Email already verified.'},
                                status=status.HTTP_200_OK)
            # Validate the OTP
            if not compare_password(otp_token, tenant.otp):
                return Response({'status': 'invalid', 'message': 'Invalid Token.'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if OTP is expired
            if check_otp_time_expired(tenant.otp_requested_at):
                return Response({'status': 'expired', 'message': 'Token has expired.'},
                                status=status.HTTP_400_BAD_REQUEST)

            # Toggle verification status if OTP is valid and has not expired
            if not tenant.is_verified:
                tenant.is_verified = True
                tenant.otp_verified_at = timezone.now()
                tenant.save()
                return Response({'status': 'verified', 'message': 'Email successfully verified.'},
                                status=status.HTTP_200_OK)

        except Tenant.DoesNotExist:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)


class ResendVerificationEmail(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def create(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
            user = User.objects.get(email=payload['email'])
            if user.profile.is_verified:
                return Response({'detail': 'Email is already verified'}, status=status.HTTP_200_OK)

            new_token = RefreshToken.for_user(user)
            new_token['email'] = user.email

            relative_link = reverse('email-verify')
            current_site = request.get_host()  # Get the current domain
            absolute_url = f'https://{current_site}{relative_link}?token={str(new_token.access_token)}'

            email_body = f'Hi {user.username},\nUse the link below to verify your email:\n\n{absolute_url}'
            data = {'email_body': email_body, 'to_email': user.email, 'email_subject': 'Verify Your Email'}

            Util.send_email(data)
            return Response({'detail': 'Verification email resent successfully'}, status=status.HTTP_200_OK)
        except (jwt.DecodeError, User.DoesNotExist) as e:
            error_message = 'Invalid token' if isinstance(e, jwt.DecodeError) else 'User with this email does not exist'
            return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST if isinstance(e,
                                                                                                       jwt.DecodeError) else status.HTTP_404_NOT_FOUND)


# class ResendVerificationEmail(generics.GenericAPIView):
#     permission_classes = [AllowAny]
#     serializer_class = ResendVerificationEmailSerializer
# 
#     def get(self, request):
#         token = request.GET.get('token')
#         if not token:
#             return Response({'error': 'Token is missing'}, status=status.HTTP_400_BAD_REQUEST)
# 
#         try:
#             payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
#             user = User.objects.get(email=payload['email'])
# 
#             if user.profile.is_verified:
#                 return Response({'detail': 'Email already verified'}, status=status.HTTP_400_BAD_REQUEST)
# 
#             new_token = RefreshToken.for_user(user)
#             new_token['email'] = user.email
# 
#             # current_site = get_current_site(request).domain
#             current_site = f"{payload['tenant']}.fastrasuite.com"
#             relative_link = reverse('email-verify')
#             absolute_url = f'https://{current_site}{relative_link}?token={str(new_token.access_token)}'
#             email_body = f'Hi {user.username},\nUse the link below to verify your email:\n{absolute_url}'
#             data = {'email_body': email_body, 'to_email': user.email, 'email_subject': 'Verify Your Email'}
# 
#             Util.send_email(data)
# 
#             return Response({'detail': 'New verification email has been sent.'}, status=status.HTTP_200_OK)
#         except (jwt.DecodeError, User.DoesNotExist) as e:
#             error_message = 'Invalid token' if isinstance(e, jwt.DecodeError) else 'User with this email does not exist'
#             return Response({'error': error_message}, status=status.HTTP_400_BAD_REQUEST if isinstance(e,
#                                                                                                        jwt.DecodeError) else status.HTTP_404_NOT_FOUND)


# class LoginView(APIView):
#     serializer_class = LoginSerializer
#     permission_classes = [AllowAny]
#
#     def post(self, request):
#         serializer = LoginSerializer(data=request.data)
#         if serializer.is_valid():
#             email = serializer.validated_data['email']
#             password = serializer.validated_data['password']
#         else:
#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
#
#         # email = request.data.get('email')
#         # password = request.data.get('password')
#         # full_host = request.get_host().split(':')[0]
#         # schema_name = full_host.split('.')[0]
#         #
#         # schema_name = slugify(company_name)
#         #
#         # with set_tenant_schema('public'):
#         #     try:
#         #         tenant_s = Tenant.objects.get(schema_name=schema_name)
#         #     except Tenant.DoesNotExist:
#         #         raise TenantNotFoundException()
#         #
#         # if not tenant.is_verified:
#         #     return Response({'error': 'Tenant not verified.'}, status=status.HTTP_400_BAD_REQUEST)
#
#         user = authenticate(request, email=email, password=password)
#         tenant_id = request.session.get('tenant_id')
#         tenant_schema_name = request.session.get('tenant_schema_name')
#         tenant_company_name = request.session.get('tenant_company_name')
#         with set_tenant_schema('public'):
#             try:
#                 tenant = Tenant.objects.get(schema_name=tenant_schema_name)
#             except Tenant.DoesNotExist:
#                 raise TenantNotFoundException()
#
#         if not tenant.is_verified:
#             return Response({'error': 'Tenant not verified.'}, status=status.HTTP_400_BAD_REQUEST)
#
#         if user is None:
#             raise InvalidCredentialsException()
#
#         refresh = RefreshToken.for_user(user)
#         refresh['tenant_id'] = tenant_id
#         refresh['schema_name'] = tenant_schema_name
#
#         return Response({
#             'refresh_token': str(refresh),
#             'access_token': str(refresh.access_token),
#             'user': {
#                 'id': user.id,
#                 'username': user.username,
#                 'email': user.email,
#             },
#             "tenant_id": tenant_id,
#             "tenant_schema_name": tenant_schema_name,
#             "tenant_company_name": tenant_company_name
#         }, status=status.HTTP_200_OK)


#
# class LoginView(APIView):
#     serializer_class = LoginSerializer
#     permission_classes = [AllowAny]
#
#     def post(self, request):
#         serializer = LoginSerializer(data=request.data)
#
#         if serializer.is_valid():
#             email = serializer.validated_data['email']
#             password = serializer.validated_data['password']
#
#             full_host = request.get_host().split(':')[0]
#             schema_name = full_host.split('.')[0]
#
#             connection.set_schema('public')
#             try:
#                 user = User.objects.get(email=email)
#             except User.DoesNotExist:
#                 return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
#             try:
#                 tenant = Tenant.objects.get(schema_name__exact=schema_name)
#             except Tenant.DoesNotExist:
#                 return Response({'error': 'Tenant not found.'},
#                                 status=status.HTTP_404_NOT_FOUND)
#
#             if not tenant.is_verified:
#                 return Response({'error': 'Tenant not verified.'}, status=status.HTTP_400_BAD_REQUEST)
#
#             connection.set_schema(schema_name)
#             try:
#                 tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)
#                 if tenant_user.password and not tenant_user.check_tenant_password(password):
#                     return Response({'error': 'Invalid credentials'},
#                                     status=status.HTTP_401_UNAUTHORIZED)
#                 connection.set_schema('public')
#                 user = authenticate(request, email=email, password=password)
#                 auth_login(request, user)
#                 refresh = RefreshToken.for_user(user)
#                 refresh['tenant_id'] = tenant_user.tenant.id
#
#                 return Response({
#                     'refresh': str(refresh),
#                     'access': str(refresh.access_token),
#                     'user': {
#                         'id': user.id,
#                         'username': user.username,
#                         'email': user.email,
#                     }
#                 }, status=status.HTTP_200_OK)
#
#             except TenantUser.DoesNotExist:
#                 return Response({'error': 'User does not have access this tenant.'},
#                                 status=status.HTTP_404_NOT_FOUND)


class RequestForgottenPasswordView(generics.GenericAPIView):
    serializer_class = RequestForgottenPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                if not user.profile.is_verified:
                    return Response({'error': 'Email is not verified.'}, status=status.HTTP_400_BAD_REQUEST)

                otp = OTP.objects.create(user=user)

                send_mail(
                    'Forgotten Password OTP',
                    f'Your OTP for forgotten password is: {otp.code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                request.session['forgotten_password_email'] = email  # Store email in session
                return Response({'detail': 'OTP has been sent to your email.'}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgottenPasswordView(generics.GenericAPIView):
    serializer_class = ForgottenPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.session.get('forgotten_password_email')
        if not email:
            return Response(
                {'error': 'No email found in session. Please initiate the forgotten password process again.'},
                status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            otp_code = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']

            try:
                user = User.objects.get(email=email)
                otp = OTP.objects.filter(user=user, code=otp_code).order_by('-created_at').first()

                if otp and otp.is_valid():
                    user.set_password(new_password)
                    user.save()
                    otp.delete()  # Delete the OTP after successful use
                    del request.session['forgotten_password_email']  # Clear the email from session
                    return Response({'detail': 'Password has been updated successfully.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.session.get('forgotten_password_email')
        if not email:
            return Response(
                {'error': 'No email found in session. Please initiate the forgotten password process again.'},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            # Invalidate any existing OTPs
            OTP.objects.filter(user=user, is_used=False).update(is_used=True)

            # Create new OTP
            otp = OTP.objects.create(user=user)

            # Send email with new OTP
            send_mail(
                'New Forgotten Password OTP',
                f'Your new OTP for forgotten password is: {otp.code}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return Response({'message': 'New OTP sent successfully'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'No user found with this email address'}, status=status.HTTP_404_NOT_FOUND)


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class UpdateCompanyProfileView(generics.UpdateAPIView):
    serializer_class = CompanyProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = (MultiPartParser, FormParser)

    def get_object(self):
        tenant = self.request.user.tenant
        company_profile, created = CompanyProfile.objects.get_or_create(tenant=tenant)
        return company_profile

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

    def handle_exception(self, exc):
        if isinstance(exc, PermissionDenied):
            return Response({"detail": "Only the admin user can update the company profile."},
                            status=status.HTTP_403_FORBIDDEN)
        return super().handle_exception(exc)


class ProtectedView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": f"Hello, {request.user.username}. You are logged in!"})
