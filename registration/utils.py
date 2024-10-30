import random

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import EmailMessage
from django.utils import timezone
from django.utils.timezone import is_aware, make_aware


class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
        email.send(fail_silently=False)


def generate_otp():
    if settings.DEBUG:
        otp = "123456"
    else:
        otp = str(random.randint(1, 999999)).zfill(6)

    hashed_otp = make_password(otp)

    return otp, hashed_otp


def check_otp_time_expired(otp_requested_at, duration=5, use_pyotp=False):
    if not is_aware(otp_requested_at):
        otp_requested_at = make_aware(otp_requested_at)

    created_at = otp_requested_at
    current_time = timezone.now()

    time_difference = current_time - created_at
    time_difference_minutes = time_difference.seconds / 60

    return time_difference_minutes > duration


def compare_password(input_password, hashed_password):
    return check_password(input_password, hashed_password)