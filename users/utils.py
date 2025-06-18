import base64
import random
import string
from django.core.mail import EmailMessage


class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
        email.send(fail_silently=False)


def generate_random_password(length=8):
    characters = string.ascii_letters + string.digits 
    password = ''.join(random.choice(characters) for _ in range(length))
    return password


def convert_to_base64(signature_file):
    image_data = signature_file.read()
    encoded_image = base64.b64encode(image_data).decode('utf-8')
    return encoded_image


if __name__ == "__main__":
    password = generate_random_password()
    print("The Password is: ", password)