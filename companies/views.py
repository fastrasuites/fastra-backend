import json
import jwt
from urllib.parse import urlparse

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect
from django.urls import reverse
#from django.core.mail import send_mail
from registration.utils import Util, make_authentication, conditional_rights_population
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
from rest_framework.parsers import MultiPartParser, FormParser,JSONParser
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.errors.exceptions import TenantNotFoundException, InvalidCredentialsException
from registration.utils import check_otp_time_expired, compare_password, set_tenant_schema, generate_tokens
from registration.models import Tenant, Domain
from registration.views import LoginView
from users.models import TenantUser

from .models import CompanyProfile
from registration.models import OTP
from .serializers import ChangeAdminPasswordSerializer, OTPVerificationSerializer, TenantSerializer, VerifyEmailSerializer, RequestForgottenPasswordSerializer, \
    ForgottenPasswordSerializer, CompanyProfileSerializer,MarkOnboardedSerializer, ResendVerificationEmailSerializer
from .utils import Util
from .permissions import IsAdminUser
from rest_framework.permissions import IsAuthenticated
from rest_framework import  permissions



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
                with schema_context("public"):
                    user = tenant.created_by
                    print("Created by user:", user)

                    if user:
                        if user.is_superuser and user.is_staff:
                            user.profile.is_verified = True
                            user.profile.save()
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

"""
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
                    tenant = user.tenants.first()
                    if tenant:
                        print(tenant)
                        print(user)
                        with tenant_context(tenant):
                            try:
                                tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)
                                print(tenant_user)
                                tenant_user.set_tenant_password(new_password)
                                tenant_user.save()
                            except TenantUser.DoesNotExist:
                                return Response({'error': 'Tenant user not found.'}, status=status.HTTP_404_NOT_FOUND)
                            except Exception as e:
                                import traceback
                                print("Unexpected error in tenant_context block:")
                                print(traceback.format_exc())
                                return Response({'error': 'Unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    otp.delete()  # Delete the OTP after successful use
                    del request.session['forgotten_password_email']  # Clear the email from session
                    return Response({'detail': 'Password has been updated successfully.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
"""

class LoginDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # email = request.query_params.get("email")
        # if not email:
        #     return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)
        #
        # user = User.objects.filter(email=email).first()
        user = request.user
        if not user:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        tenant_user = make_authentication(user.id, all_user_details=True)
        if not tenant_user:
            return Response({'detail': 'User not found in any tenant schema.'}, status=status.HTTP_404_NOT_FOUND)

        tenant_id = tenant_user.id
        tenant_schema_name = tenant_user.tenant.schema_name
        tenant_company_name = tenant_user.tenant.company_name

        try:
            with set_tenant_schema('public'):
                tenant = Tenant.objects.get(schema_name=tenant_schema_name)
        except Tenant.DoesNotExist:
            return Response({'detail': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Unexpected error accessing tenant: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            conditional_rights_population()
            data = LoginView().get_access_groups(tenant_schema_name, user)
        except Exception as e:
            return Response({'detail': f'Failed to fetch user access groups: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'user': {
                "tenant_user_id": tenant_user.id,
                "username": tenant_user.user.username,
                "first_name": tenant_user.user.first_name,
                "last_name": tenant_user.user.last_name,
                "user_image": tenant_user.user_image,
            },
            "tenant_id": tenant_id,
            "tenant_schema_name": tenant_schema_name,
            "tenant_company_name": tenant_company_name,
            "isOnboarded": tenant.is_onboarded,
            "user_accesses": data
        }, status=status.HTTP_200_OK)

class RequestForgottenPasswordView(generics.GenericAPIView):
    serializer_class = RequestForgottenPasswordSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            #try:
                #user = User.objects.get(email=email)
                #user = User.objects.get(email=email, is_superuser=True, is_staff=True)
            user = None
            try:
                with schema_context("public"):
                   user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)

            if not (user.is_superuser and user.is_staff):
            # Notify tenant admin
                # schema_name = connection.schema_name

                _, schema_name, _, _ = make_authentication(user.id)
                try:
                    tenant_details = Tenant.objects.get(schema_name=schema_name)
                except Tenant.DoesNotExist:
                    return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

                tenant_user_profile = tenant_details.created_by

                email_body = (
                    f"Hi {tenant_details.company_name},\n\n"
                    f"We received a request from your employee ({user.email}) for a password reset. "
                    f"Please login to your dashboard to reset the user's password.\n\n"
                    f"If you did not approve this, please ignore this email or contact support.\n\n"
                    f"Thanks,\nThe fastrasuite Team"
                )

                email_data = {
                    'email_body': email_body,
                    'to_email': tenant_user_profile.email,
                    'email_subject': 'Employee Password Reset Request'
                }

                try:
                    Util.send_email(email_data)
                except Exception:
                    import traceback
                    print("Failed to send email to tenant admin")
                    print(traceback.format_exc())
                    return Response({'error': 'Error sending email to tenant admin.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                return Response({'detail': 'Request sent to tenant admin for approval.'}, status=status.HTTP_200_OK)
            
            if not user.profile.is_verified:
                return Response({'error': 'Email is not verified.'}, status=status.HTTP_400_BAD_REQUEST)
            
            #otp = OTP.objects.create(user=user)

            try:
                otp = OTP.objects.create(user=user)
                print(f"OTP created: {otp.code}")  # Confirm the object and code
            except Exception as e:
                import traceback
                print("Failed to create OTP")
                print(traceback.format_exc())  # Full error stack trace
                return Response({'error': 'Internal error creating OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            email_body = (
                f"Hi {user.username},\n\n"
                f"We received a request to reset your password. Use the OTP (One-Time Password) below to proceed:\n\n"
                f"OTP: {otp.code}\n\n"
                f"This OTP is valid for the next 10 minutes.\n\n"
                f"If you did not request a password reset, please ignore this email or contact support.\n\n"
                f"Thanks,\n"
                f"The fastrasuite Team"
            )

            email_data = {
                'email_body': email_body,
                'to_email': user.email,
                'email_subject': 'Your Password Reset OTP'
            }

            """Util.send_email(
                'Forgotten Password OTP',
                f'Your OTP for forgotten password is: {otp.code}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )"""

            #Util.send_email(email_data)
            try:
                Util.send_email(email_data)
            except Exception as e:
                import traceback
                print("Failed to send email")
                print(traceback.format_exc())
                return Response({'error': 'Error sending email, please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            request.session['forgotten_password_email'] = email  # Store email in session
            return Response({'detail': 'OTP has been sent to your email.'}, status=status.HTTP_200_OK)
            #except User.DoesNotExist:
                #return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPView(generics.GenericAPIView):
    serializer_class = OTPVerificationSerializer 
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response(
                {'error': 'Email is required for OTP verification.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            otp_code = serializer.validated_data['otp']
            try:
                user = User.objects.get(email=email)
                otp = OTP.objects.filter(user=user, code=otp_code).order_by('-created_at').first()

                if otp and otp.is_valid():
                    otp.is_used = True
                    otp.save()
                    return Response({'detail': 'OTP verified successfully.'}, status=status.HTTP_200_OK)
                else:
                    return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({'error': 'No user found with this email address.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(generics.GenericAPIView):
    serializer_class = ForgottenPasswordSerializer 
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response(
                {'error': 'Email is required for OTP verification.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = OTP.objects.filter(user__email=email, is_used=True).order_by('-created_at').first()
        print("i got here", otp)
        if not otp:
            print("i got here 2")
            return Response({'error': 'OTP verification required.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            new_password = serializer.validated_data['new_password']
            confirm_password = serializer.validated_data['confirm_password']

            if new_password != confirm_password:
                return Response({'error': 'Passwords do not match.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()

                tenant = user.tenants.first()
                #tenant = user.tenants.filter(schema_name=connection.schema_name).first()
                print("tenant: ",tenant)
                if tenant:
                    with tenant_context(tenant):
                        try:
                            tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)
                            tenant_user.set_tenant_password(new_password)
                            tenant_user.save()
                        except TenantUser.DoesNotExist:
                            return Response({'error': 'Tenant user not found.'}, status=status.HTTP_404_NOT_FOUND)
                        except Exception:
                            import traceback
                            print(traceback.format_exc())
                            return Response({'error': 'Unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                OTP.objects.filter(user=user).delete()

                return Response({'detail': 'Password has been updated successfully.'}, status=status.HTTP_200_OK)

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
            #otp = OTP.objects.create(user=user)
            try:
                otp = OTP.objects.create(user=user)
                print(f"OTP created: {otp.code}")
            except Exception as e:
                import traceback
                print("Failed to create OTP")
                print(traceback.format_exc())
                return Response({'error': 'Internal error creating OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            email_body = (
                f"Hi {user.username},\n\n"
                f"You recently requested to reset your password.\n\n"
                f"Your One-Time Password (OTP) is: {otp.code}\n\n"
                f"This code will expire in 10 minutes. Please do not share this code with anyone.\n\n"
                f"If you did not initiate this request, please ignore this message or contact Fastra support immediately.\n\n"
                f"Best regards,\n"
                f"The FastraSuite Team"
            )

            email_data = {
                'email_body': email_body,
                'to_email': user.email,
                'email_subject': 'Password Reset OTP'
            }


            # Send email with new OTP
            """send_mail(
                'New Forgotten Password OTP',
                f'Your new OTP for forgotten password is: {otp.code}',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            """
            Util.send_email(email_data)
            return Response({'message': 'New OTP sent successfully'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'No user found with this email address'}, status=status.HTTP_404_NOT_FOUND)


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer

class UpdateCompanyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = CompanyProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self):
        tenant_id = self.request.user.id

        tenant_user = TenantUser.objects.filter(user_id=tenant_id).first()
        if not tenant_user:
            raise PermissionDenied(detail='Tenant user not found.')

        tenant = tenant_user.tenant
        company_profile, created = CompanyProfile.objects.get_or_create(tenant=tenant)
        return company_profile

    def update(self, request, *args, **kwargs):
        # print("Incoming data:", request.data)

        # Create a new dictionary to avoid copying file objects
        data = {}

        # Handle file uploads separately
        files_data = {}
        if hasattr(request, 'FILES'):
            for key, file_obj in request.FILES.items():
                # Map 'logo' to 'logo_image' for the serializer
                if key == 'logo':
                    files_data['logo_image'] = file_obj
                else:
                    files_data[key] = file_obj

        # Process non-file data
        for key, value in request.data.items():
            # Skip file fields that are already handled
            if key in request.FILES:
                continue

            # Handle roles specially
            if key == 'roles':
                if isinstance(value, list):
                    value = value[0]  # Extract JSON string from list
                try:
                    parsed_roles = json.loads(value) if isinstance(value, str) else value
                    data[key] = parsed_roles
                except (json.JSONDecodeError, TypeError):
                    return Response({"error": "Invalid JSON in roles"}, status=400)
            else:
                # Convert single-item lists to single values
                if isinstance(value, list) and len(value) == 1:
                    data[key] = value[0]
                else:
                    data[key] = value

        # Merge file data with regular data
        data.update(files_data)

        # print("Clean dict data:", data)

        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        # print("Logo in response:", serializer.data.get("logo"))
        return Response(serializer.data)

    def handle_exception(self, exc):
        if isinstance(exc, PermissionDenied):
            return Response({"detail": "Only the admin user can update the company profile."},
                            status=status.HTTP_403_FORBIDDEN)
        return super().handle_exception(exc)



#class UpdateCompanyProfileView(generics.UpdateAPIView):
"""class UpdateCompanyProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = CompanyProfileSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    parser_classes = (MultiPartParser, FormParser)

    def get_object(self):
        tenant_id = self.request.user.id

        tenant_user = TenantUser.objects.filter(user_id=tenant_id).first()
        if not tenant_user:
            raise PermissionDenied(detail='Tenant user not found.')
            #return Response({'error': 'Tenant user not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        tenant = tenant_user.tenant
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
"""

class ChangeAdminPassword(generics.GenericAPIView):
    serializer_class = ChangeAdminPasswordSerializer 
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            new_password = serializer.validated_data['new_password']
            old_password = serializer.validated_data['old_password']

            user = request.user  # ✅ Use authenticated user
            print("schema_name:", connection.schema_name)

            # Retrieve tenant
            tenant = user.tenants.filter(schema_name=connection.schema_name).first()
            print("The Tenant ", tenant)
            if tenant:
                with tenant_context(tenant):
                    try:
                        tenant_user = TenantUser.objects.get(user_id=user.id, tenant=tenant)

                        if not tenant_user.check_tenant_password(old_password):
                            return Response({'error': 'Incorrect old password.'}, status=status.HTTP_400_BAD_REQUEST)

                        # Update TenantUser password
                        tenant_user.set_tenant_password(new_password)
                        tenant_user.temp_password = None
                        tenant_user.save()

                    except TenantUser.DoesNotExist:
                        return Response({'error': 'Tenant user record not found.'}, status=status.HTTP_404_NOT_FOUND)
                    except Exception as e:
                        import traceback
                        print(traceback.format_exc())
                        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Update User password in public schema
            with schema_context('public'):
                print("I am in here 2")
                if not user.check_password(old_password):
                    return Response({'error': 'Incorrect old password (public).'}, status=status.HTTP_400_BAD_REQUEST)
                user.set_password(new_password)
                user.save()

            return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MarkOnboardedView(generics.GenericAPIView):
    serializer_class = MarkOnboardedSerializer
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = request.user
            tenant = user.tenants.filter(schema_name=connection.schema_name).first()

            if tenant:
                with tenant_context(tenant):
                    tenant.is_onboarded = True
                    tenant.save()

                    return Response({
                        "id": tenant.id,
                        "is_onboarded": tenant.is_onboarded
                    }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class OnboardingStatusView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        tenant = user.tenants.filter(schema_name=connection.schema_name).first()

        if tenant:
            return Response({'is_onboarded': tenant.is_onboarded}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)

class ProtectedView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"message": f"Hello, {request.user.username}. You are logged in!"})
