from rest_framework.views import APIView
from django.shortcuts import render, redirect
from django.urls import reverse
from rest_framework.response import Response
from rest_framework import viewsets, generics
from rest_framework import status
from django.utils.text import slugify
from django.contrib.auth import login, authenticate, get_user_model
from django.core.management import call_command
from drf_spectacular.utils import extend_schema, extend_schema_view
from core.errors.exceptions import TenantNotFoundException, InvalidCredentialsException
from .models import Tenant, Domain
from .serializers import NewGroupSerializer, TenantRegistrationSerializer, LoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import Util, set_tenant_schema
from django.contrib.sites.shortcuts import get_current_site
import jwt
from django.conf import settings
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from django.contrib.auth.models import Group


@extend_schema_view(
    create=extend_schema(
        summary="Register a new tenant",
        description="Registers a new tenant and sends an email verification link.",
        responses={
            201: "Tenant created successfully.",
            400: "Validation error or registration failed."
        }
    )
)
class TenantRegistrationViewSet(viewsets.ViewSet):
    serializer_class = TenantRegistrationSerializer
    permission_classes = [AllowAny]

    @transaction.atomic
    def create(self, request):
        serializer = self.serializer_class(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            tenant, otp = serializer.save()
            call_command('create-default-config-schema', tenant.schema_name)

            api_base_domain = settings.API_BASE_DOMAIN
            sanitized_name = slugify(tenant.schema_name, allow_unicode=True)

            domain = Domain.objects.create(
                domain=f"{sanitized_name}.{api_base_domain}",
                tenant=tenant,
                is_primary=True
            )
            frontend_url = settings.FRONTEND_URL
            verification_url = f"{frontend_url}/verify-email?token={otp}&tenant={tenant.schema_name}"

            # email_body = (
            #     f"Hi {tenant.company_name},\n\n"
            #     f"Thank you for registering. Your OTP for email verification is: {otp}\n\n"
            #     f"Please use this OTP to verify your email address and complete your registration."
            # )
            email_body = (
                f"Hi {tenant.company_name},\n\n"
                f"Thank you for registering. To complete your registration, please verify your email by clicking the "
                f"link below:\n\n"
                f"{verification_url}\n\n"
                f"If you did not register for an account, please ignore this email."
            )
            email_data = {
                'email_body': email_body,
                'to_email': tenant.created_by.email,
                'email_subject': 'Verify Your Email'
            }
            Util.send_email(email_data)
            return Response({
                'detail': 'Tenant created successfully. Please verify your email with the OTP sent.',
                'tenant_url': f"https://{domain.domain}"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(e)
            transaction.set_rollback(True)
            return Response({'detail': f'An error occurred during registration. Please try again. {str(e)}'},
                            status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    summary="Login endpoint",
    description="Authenticates a user and returns access and refresh tokens.",
    responses={
        200: "Login successful.",
        400: "Invalid credentials or validation error."
    }
)
class LoginView(APIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # email = request.data.get('email')
        # password = request.data.get('password')
        # full_host = request.get_host().split(':')[0]
        # schema_name = full_host.split('.')[0]
        #
        # schema_name = slugify(company_name)
        #
        # with set_tenant_schema('public'):
        #     try:
        #         tenant_s = Tenant.objects.get(schema_name=schema_name)
        #     except Tenant.DoesNotExist:
        #         raise TenantNotFoundException()
        #
        # if not tenant.is_verified:
        #     return Response({'error': 'Tenant not verified.'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email, password=password)
        tenant_id = request.session.get('tenant_id')
        tenant_schema_name = request.session.get('tenant_schema_name')
        tenant_company_name = request.session.get('tenant_company_name')
        with set_tenant_schema('public'):
            try:
                tenant = Tenant.objects.get(schema_name=tenant_schema_name)
            except Tenant.DoesNotExist:
                raise TenantNotFoundException()

        if not tenant.is_verified:
            return Response({'error': 'Tenant not verified.'}, status=status.HTTP_400_BAD_REQUEST)

        if user is None:
            raise InvalidCredentialsException()

        refresh = RefreshToken.for_user(user)
        refresh['tenant_id'] = tenant_id
        refresh['schema_name'] = tenant_schema_name

        return Response({
            'refresh_token': str(refresh),
            'access_token': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
            },
            "tenant_id": tenant_id,
            "tenant_schema_name": tenant_schema_name,
            "tenant_company_name": tenant_company_name
        }, status=status.HTTP_200_OK)



# START THE NEW GROUP VIEWSET
class NewGroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = NewGroupSerializer
    permission_classes = [AllowAny]
    search_fields = ['name']

    def perform_create(self, serializer):
        serializer.save()
# END THE NEW GROUP VIEWSET
