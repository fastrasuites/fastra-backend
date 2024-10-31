from rest_framework.views import APIView
from django.shortcuts import render, redirect
from django.urls import reverse
from rest_framework.response import Response
from rest_framework import viewsets, generics
from rest_framework import status
from django.utils.text import slugify
from django.contrib.auth import login, authenticate, get_user_model
from .models import Tenant, Domain
from .serializers import TenantRegistrationSerializer
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
from django.db import transaction
from django_tenants.utils import schema_context, tenant_context
from rest_framework.permissions import AllowAny


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

            api_base_domain = settings.API_BASE_DOMAIN
            sanitized_name = slugify(tenant.schema_name, allow_unicode=True)

            domain = Domain.objects.create(
                domain=f"{sanitized_name}.{api_base_domain}",
                tenant=tenant,
                is_primary=True
            )
            frontend_url = settings.FRONTEND_URL
            verification_url = f"{frontend_url}/email-verify?token={otp}&tenant={tenant.schema_name}"

            # email_body = (
            #     f"Hi {tenant.company_name},\n\n"
            #     f"Thank you for registering. Your OTP for email verification is: {otp}\n\n"
            #     f"Please use this OTP to verify your email address and complete your registration."
            # )
            email_body = (
                f"Hi {tenant.company_name},\n\n"
                f"Thank you for registering. To complete your registration, please verify your email by clicking the link below:\n\n"
                f"{verification_url}\n\n"
                f"If you did not register for an account, please ignore this email."
            )
            print(email_body)
            email_data = {
                'email_body': email_body,
                'to_email': tenant.created_by.email,
                'email_subject': 'Verify Your Email'
            }
            # Util.send_email(email_data)
            return Response({
                'detail': 'Tenant created successfully. Please verify your email with the OTP sent.',
                'tenant_url': f"https://{domain.domain}"
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            print(e)
            transaction.set_rollback(True)
            return Response({'detail': 'An error occurred during registration. Please try again.'},
                            status=status.HTTP_400_BAD_REQUEST)