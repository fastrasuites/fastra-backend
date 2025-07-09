from rest_framework.views import APIView
from django.shortcuts import render, redirect
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import status
from django.utils.text import slugify
from django.contrib.auth import authenticate
from django.core.management import call_command
from drf_spectacular.utils import extend_schema, extend_schema_view
from core.errors.exceptions import TenantNotFoundException, InvalidCredentialsException
from registration.config import DESIRED_INVENTORY_MODELS, DESIRED_PURCHASE_MODELS
from .models import Tenant, Domain
from .serializers import AccessRightSerializer, TenantRegistrationSerializer, LoginSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import Util, set_tenant_schema
from django.conf import settings
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context
from rest_framework.permissions import AllowAny
from rest_framework import permissions
from shared.utils.email_service import EmailService
from shared.viewsets.soft_delete_viewset import SoftDeleteWithModelViewSet
from .models import AccessRight
from django.contrib.contenttypes.models import ContentType



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
        email_service = EmailService()

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

            context = {
                'company': tenant,
                'company_name': tenant.company_name,
                'activation_link': verification_url
            }

            success = email_service.send_email(
                subject='Verify Your Email',
                template_name='email/company_welcome.html',
                context=context,
                recipient_list=[tenant.created_by.email]
            )

            if success:
                return Response({
                    'detail': 'Tenant created successfully. Please verify your email with the OTP sent.',
                    'tenant_url': f"https://{domain.domain}"
                }, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    {
                        'detail': f'An error occurred during registration. Please try again'
                    }, status=status.HTTP_400_BAD_REQUEST
                )
            # email_body = (
            #     f"Hi {tenant.company_name},\n\n"
            #     f"Thank you for registering. To complete your registration, please verify your email by clicking the "
            #     f"link below:\n\n"
            #     f"{verification_url}\n\n"
            #     f"If you did not register for an account, please ignore this email."
            # )
            # email_data = {
            #     'email_body': email_body,
            #     'to_email': tenant.created_by.email,
            #     'email_subject': 'Verify Your Email'
            # }
            # Util.send_email(email_data)
            # return Response({
            #     'detail': 'Tenant created successfully. Please verify your email with the OTP sent.',
            #     'tenant_url': f"https://{domain.domain}"
            # }, status=status.HTTP_201_CREATED)

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


