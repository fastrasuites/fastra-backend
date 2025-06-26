import base64
import random
import string
from django.core.mail import EmailMessage
import mimetypes
from rest_framework.exceptions import APIException

from users.models import AccessGroupRight
from django.db.models import Max
from django.db import connection

class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
        email.send(fail_silently=False)


def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits 
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


def convert_to_base64(signature_file, max_size=5 * 1024 * 1024):
    mime_type, _ = mimetypes.guess_type(signature_file.name)
    if mime_type not in ['image/png', 'image/jpeg', 'image/jpg']:
        raise APIException(detail="Invalid file type. Only PNG and JPEG images are allowed.")
    
    # Validate file size
    if signature_file.size > max_size:
        raise APIException(detail=f"File size exceeds the maximum limit of {max_size // (1024 * 1024)} MB.")

    image_data = signature_file.read()
    encoded_image = base64.b64encode(image_data).decode('utf-8')
    return encoded_image


def generate_access_code_for_access_group(app_name, group_name):
    app_abv = app_name.upper()[:3]
    group_abv = group_name.upper()[:3]
    access_code = f"{app_abv}-{group_abv}-"    

    max_num = AccessGroupRight.get_next_id()
    if max_num is not None and max_num != 0:
        max_num += 1
        last_digits = str(max_num).zfill(4)        
        access_code = f"{app_abv}-{group_abv}-{last_digits}"
        return access_code
    access_code = f"{app_abv}-{group_abv}-0001"
    return access_code


if __name__ == "__main__":
    password = generate_random_password()
    print("The Password is: ", password)
    print(generate_access_code_for_access_group("PURCHASE", "MANAGER"))