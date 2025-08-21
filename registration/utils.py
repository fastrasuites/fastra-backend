import random

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMessage
from django.utils import timezone
from django.utils.timezone import is_aware, make_aware
from django.db import connection
from contextlib import contextmanager

from rest_framework_simplejwt.tokens import RefreshToken

from registration.config import RIGHTS
from registration.models import AccessRight, Tenant
from users.models import TenantUser
from django_tenants.utils import schema_context
import logging



class Util:
    @staticmethod
    def send_email(data):
        try:
            email = EmailMessage(subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
            email.send(fail_silently=False)
        except Exception as e:
            # Log or handle exception as needed
            print(f"Error sending email: {e}")


def generate_otp():
    if settings.DEBUG:
        otp = "123456"
    else:
        otp = str(random.randint(1, 999999)).zfill(6)

    hashed_otp = make_password(otp)

    return otp, hashed_otp


def check_otp_time_expired(otp_requested_at, duration=60, use_pyotp=False):
    if not is_aware(otp_requested_at):
        otp_requested_at = make_aware(otp_requested_at)

    created_at = otp_requested_at
    current_time = timezone.now()

    time_difference = current_time - created_at
    time_difference_minutes = time_difference.seconds / 60

    return time_difference_minutes > duration


def compare_password(input_password, hashed_password):
    return check_password(input_password, hashed_password)


@contextmanager
def set_tenant_schema(schema_name):
    connection.set_schema(schema_name)
    try:
        yield
    finally:
        connection.set_schema('public')




def generate_tokens(user):
    refresh = RefreshToken.for_user(user)

    return str(refresh.access_token), str(refresh)




logger = logging.getLogger(__name__)

def make_authentication(userid, all_user_details=False):
    with schema_context('public'):
        all_tenants = Tenant.objects.all()
        
        for tenant in all_tenants:
            try:
                with schema_context(tenant.schema_name):
                    if TenantUser.objects.filter(user_id=userid).exists():
                        tenant_user = TenantUser.objects.get(user_id=userid)
                        if all_user_details:
                            return tenant_user
                        return tenant_user.id, tenant.schema_name, tenant.company_name, tenant_user.user_image
            except TenantUser.DoesNotExist:
                logger.warning(f"User {userid} not found in schema {tenant.schema_name}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error in schema '{tenant.schema_name}': {str(e)}")
                continue
        
        return None  


def conditional_rights_population():
    if not AccessRight.objects.exists():
        rights_obj_list = [AccessRight(name=right) for right in RIGHTS]
        created_rights = AccessRight.objects.bulk_create(rights_obj_list)
        return created_rights
    return None