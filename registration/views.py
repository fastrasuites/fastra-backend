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
        serializer = TenantRegistrationSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            # Create tenant and user
            tenant = serializer.save()
            
            # Set up domain
            frontend_url = request.data.get('frontend_url', 'http://localhost:8000')
            parsed_url = urlparse(frontend_url)
            frontend_domain = parsed_url.netloc.split(':')[0]
            sanitized_name = slugify(tenant.schema_name, allow_unicode=True)
            
            domain = Domain.objects.create(
                domain=f"{sanitized_name}.{frontend_domain}",
                tenant=tenant,
                is_primary=True
            )

            # Retrieve the user (now associated with the tenant)
            user = tenant.user

            # Perform any additional tenant-specific setup
            with tenant_context(tenant):
                # Add any tenant-specific setup here
                pass

            # Generate and send verification email
            token = RefreshToken.for_user(user)
            token['email'] = user.email
            verification_url = f'https://{domain.domain}/email-verify?token={str(token.access_token)}'

            email_body = f'Hi {tenant.company_name},\n\nUse the link below to verify your email:\n{verification_url}'
            email_data = {
                'email_body': email_body,
                'to_email': user.email,
                'email_subject': 'Verify Your Email'
            }
            Util.send_email(email_data)

            return Response({
                'detail': 'Tenant created successfully. Please confirm your email address.',
                'tenant_url': f"http://{domain.domain}"
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
