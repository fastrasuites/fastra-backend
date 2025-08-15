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
from registration.config import DESIRED_INVENTORY_MODELS, DESIRED_PURCHASE_MODELS
from users.models import AccessGroupRight, AccessGroupRightUser, TenantUser
from users.serializers import AccessGroupRightSerializer
from .models import Tenant, Domain
from .serializers import AccessRightSerializer, TenantRegistrationSerializer, LoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import Util, conditional_rights_population, make_authentication, set_tenant_schema
from django.contrib.sites.shortcuts import get_current_site
import jwt
from django.conf import settings
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from django.contrib.auth.models import Group
from shared.viewsets.soft_delete_search_viewset import SoftDeleteWithModelViewSet
from .models import AccessRight
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password


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

    def get_access_groups(self, tenant_schema_name, user):
        data = []
        # Get their accesses
        with schema_context(tenant_schema_name):
            if user.is_staff is True and user.is_superuser is True:
                data.append({
                    "application": "all_apps",
                    "access_groups": "all_access_groups"
                })
                return data

            user_access_codes = AccessGroupRightUser.objects.filter(user_id=user.id).values('access_code').distinct()
            user_access_codes = [item['access_code'] for item in user_access_codes]

            applications = AccessGroupRight.objects.filter(access_code__in=user_access_codes).values('application').distinct()
            applications = [item["application"] for item in applications]

            if not applications:
                return []

            exclude_fields = {'date_created', 'date_updated', 'application', "id"}

            for app in applications:
                access_groups = AccessGroupRight.objects.filter(access_code__in=user_access_codes, application=app)
                
                if not access_groups.exists():
                    continue  # Skip applications with no access groups

                serialized = AccessGroupRightSerializer(access_groups, many=True)

                cleaned_data = [
                    {k: v for k, v in item.items() if k not in exclude_fields}
                    for item in serialized.data
                ]

                data.append({
                    "application": app,
                    "access_groups": cleaned_data
                })
            return data


    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        password = serializer.validated_data['password']

        user = User.objects.filter(email=email).first()
        if user is None:
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        tenant_info = make_authentication(user.id)
        if tenant_info is None:
            return Response({'detail': 'User not found in any tenant schema.'}, status=status.HTTP_404_NOT_FOUND)

        tenant_id, tenant_schema_name, tenant_company_name, tenant_user_image = tenant_info

        if not check_password(password, user.password):
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            with set_tenant_schema('public'):
                tenant = Tenant.objects.get(schema_name=tenant_schema_name)
        except Tenant.DoesNotExist:
            return Response({'detail': 'Tenant not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Unexpected error accessing tenant: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not tenant.is_verified:
            return Response({'error': 'Tenant not verified.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate token
        refresh = RefreshToken.for_user(user)
        refresh['tenant_id'] = tenant_id
        refresh['schema_name'] = tenant_schema_name

        try:
            conditional_rights_population()
            data = self.get_access_groups(tenant_schema_name, user)
        except Exception as e:
            return Response({'detail': f'Failed to fetch user access groups: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'refresh_token': str(refresh),
            'access_token': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'user_image': tenant_user_image,
            },
            "tenant_id": tenant_id,
            "tenant_schema_name": tenant_schema_name,
            "tenant_company_name": tenant_company_name,
            "isOnboarded": tenant.is_onboarded,
            "user_accesses": data
        }, status=status.HTTP_200_OK)



# START THE APPLICATION, APPLICATION MODULE AND ACCESS RIGHTS VIEWSETS 
class ApplicationViewSet(SoftDeleteWithModelViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        inventory_results = ContentType.objects.filter(
        app_label='inventory',
        model__in=DESIRED_INVENTORY_MODELS
        )
        # Query for purchase models
        purchase_results = ContentType.objects.filter(
            app_label='purchase',
            model__in=DESIRED_PURCHASE_MODELS
        )

        # Sending the Available Access rights to display
        access_rights = AccessRight.objects.filter(is_hidden=False)
        access_rights_data = AccessRightSerializer(access_rights, many=True).data

        # Combine results into a structured format
        data = {
            "applications": [
                {"INVENTORY": [item.model for item in inventory_results]},
                {"PURCHASE": [item.model for item in purchase_results]}
                ],
            "access_rights": access_rights_data
            }
        
        return Response(data, status=status.HTTP_200_OK)
    

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if Application.objects.filter(name__iexact=validated_data["name"]).exists():
            return Response({"detail": "The application with this name already exists."}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AccessRightViewSet(SoftDeleteWithModelViewSet):
    queryset = AccessRight.objects.filter(is_hidden=False)
    permission_classes = []
    serializer_class = AccessRightSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        if AccessRight.objects.filter(name__iexact=validated_data["name"]).exists():
            return Response({"detail": "The access right with this name already exists."}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


