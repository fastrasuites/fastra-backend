from rest_framework.views import APIView
from django.shortcuts import render, redirect
from django.urls import reverse
from rest_framework.response import Response
from rest_framework import viewsets, generics
from rest_framework import status
from django.utils.text import slugify
from django.contrib.auth import login, authenticate, get_user_model
from .models import CompanyProfile, OTP
from registration.models import Tenant, Domain
from .serializers import TenantSerializer, LoginSerializer, \
    RequestForgottenPasswordSerializer, ForgottenPasswordSerializer, CompanyProfileSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import Util
from django.contrib.sites.shortcuts import get_current_site
import jwt
from django.conf import settings
from urllib.parse import urlparse
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_decode
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.exceptions import PermissionDenied
from .permissions import IsAdminUser
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context
from rest_framework.permissions import AllowAny

class VerifyEmail(generics.GenericAPIView):
    permission_classes = [AllowAny]
    def get(self, request):
        token = request.GET.get('token')
        # frontend_url = request.GET.get('frontend_url', 'http://localhost:3000')
        # current_site = get_current_site(self.request).domain

        if not token:
            return Response({'error': 'No token provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user = User.objects.get(email=payload['email'])

            if not user.profile.is_verified:
                user.profile.is_verified = True
                user.profile.save()
                status_message = 'Email successfully verified'
            else:
                status_message = 'Email already verified'

            # Construct tenant-specific frontend URL
            tenant_subdomain = payload['tenant']  # Assuming tenant info is included in the token
            frontend_url = f"https://{tenant_subdomain}.fastrasuite.com/email-verify-status"

            # Redirect with status and token
            redirect_url = f"{frontend_url}?status={status_message}&token={token}"
            return redirect(redirect_url)

        except jwt.ExpiredSignatureError:
            # Redirect with expiration status and token for resending
            tenant_subdomain = payload['tenant'] if 'tenant' in locals() else 'default'  # Handle case if tenant is not found
            frontend_url = f"https://{tenant_subdomain}.fastrasuite.com/email-verify-status"
            redirect_url = f"{frontend_url}?status=expired&token={token}"
            return redirect(redirect_url)
        except jwt.DecodeError:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'error': 'User does not exist'}, status=status.HTTP_400_BAD_REQUEST)
        
class ResendVerificationEmail(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.GET.get('token')
        if not token:
            return Response({'error': 'Token is missing'}, status=status.HTTP_400_BAD_REQUEST)
        
        
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
            user = User.objects.get(email=payload['email'])

            if user.profile.is_verified:
                return Response({'detail': 'Email already verified'}, status=status.HTTP_400_BAD_REQUEST)

            new_token = RefreshToken.for_user(user)
            new_token['email'] = user.email

            # current_site = get_current_site(request).domain
            current_site = f"{payload['tenant']}.fastrasuite.com"
            relativeLink = reverse('email-verify')
            absurl = f'https://{current_site}{relativeLink}?token={str(new_token.access_token)}'
            email_body = f'Hi {user.username},\nUse the link below to verify your email:\n{absurl}'
            data = {'email_body': email_body, 'to_email': user.email, 'email_subject': 'Verify Your Email'}

            Util.send_email(data)

            return Response({'detail': 'New verification email has been sent.'}, status=status.HTTP_200_OK)
        except jwt.DecodeError:
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'error': 'User with this email does not exist'}, status=status.HTTP_404_NOT_FOUND)


class LoginView(APIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            user = authenticate(request, email=email, password=password)

            if user is not None:
                if user.profile.is_verified:
                    login(request, user)
                    refresh = RefreshToken.for_user(user)
                    print(refresh.payload)
                    # Get the tenant associated with the user
                    try:
                        # tenant = Tenant.objects.get(user=user)
                        # domain = Domain.objects.get(tenant=tenant)

                        # refresh['tenant_id'] = tenant.id
                        # refresh['domain'] = domain.domain

                        print(refresh.payload)

                        # Construct the tenant-specific URL
                        # tenant_url = f"{domain.domain}"

                        # Set the schema to be used in the current request
                        # connection.set_schema(tenant.schema_name)
                        # with schema_context(tenant.schema_name):
                            # pass

                        return Response({
                                'refresh': str(refresh),
                                'access': str(refresh.access_token),
                                'user': {
                                    'id': user.id,
                                    'username': user.username,
                                    'email': user.email,
                                },
                                # 'redirect_url': tenant_url
                            }, status=status.HTTP_200_OK)
                        
                    except (Tenant.DoesNotExist, Domain.DoesNotExist):
                        return Response({'error': 'Tenant or domain not found for this user.'},
                                        status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({'error': 'Please verify your email before logging in.'},
                                    status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({'error': 'Invalid credentials'},
                                status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RequestForgottenPasswordView(APIView):
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


class ForgottenPasswordView(APIView):
    serializer_class = ForgottenPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.session.get('forgotten_password_email')
        if not email:
            return Response({'error': 'No email found in session. Please initiate the forgotten password process again.'}, status=status.HTTP_400_BAD_REQUEST)

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


class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        email = request.session.get('forgotten_password_email')
        if not email:
            return Response({'error': 'No email found in session. Please initiate the forgotten password process again.'}, status=status.HTTP_400_BAD_REQUEST)

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