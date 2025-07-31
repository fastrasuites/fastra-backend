

from inventory.models import IncomingProduct, IncomingProductItem, StockMove
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=IncomingProduct)
def create_incoming_product_stock_move(sender, instance, created, **kwargs):
    """Create stock move when an incoming inventory record item is created"""
    if created:
        if instance.status == "done":
            items = IncomingProductItem.objects.filter(incoming_product_id=instance.incoming_product_id)
            product_item_list = [
                StockMove(
                    product=item.product,
                    unit_of_measure=item.product.unit_of_measure,
                    quantity=item.quantity_received,
                    move_type='IN',
                    source_document_id=item.incoming_product_id,  # replace with the appropriate inventory record id
                    source_location=instance.source_location,
                    destination_location=instance.destination_location,
                    # replace with the appropriate inventory record location
                    moved_by=instance.incoming_record.created_by  # replace with the appropriate inventory record creator
                ) for item in items 
            ]
            IncomingProductItem.objects.bulk_create(product_item_list)