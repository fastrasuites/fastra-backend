from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.db.models import Max, F, Value
from django.db.models.functions import Substr, Cast
from django.db import models

from inventory.models import DeliveryOrder, ReturnIncomingProduct


def generate_delivery_order_unique_id(source_location):
    # Query to get the maximum unique_order_id based on the numeric part
    max_unique_order_id = DeliveryOrder.objects.count()

    if max_unique_order_id is not None:
        max_unique_order_id += 1
        max_unique_order_id = str(max_unique_order_id).zfill(4)
        
        source_location = source_location[:4].upper()
        id = f"{source_location}-OUT-{max_unique_order_id}"
        return id
    id = f"{source_location[:4]}-OUT-0001"
    return id


def generate_returned_record_unique_id(delivery_order_id):
    if delivery_order_id is not None:
        id = f"RETD-{delivery_order_id}"
        return id
    return "Expects an ID but none was given"


def generate_returned_incoming_product_unique_id(location_code):
    # Query to get the maximum unique_order_id based on the numeric part
    max_unique_order_id = ReturnIncomingProduct.objects.annotate(
        numeric_id=Cast(Substr('unique_id', 8, 4), output_field=models.IntegerField())
    ).aggregate(max_id=Max('numeric_id'))['max_id']

    if max_unique_order_id is not None:
        max_unique_order_id += 1
        max_unique_order_id = str(max_unique_order_id).zfill(4)
        
        id = f"{location_code}RET{max_unique_order_id}"
        return id
    id = f"{location_code}RET0001"
    return id
