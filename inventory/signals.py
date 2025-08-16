

from inventory.models import BackOrder, BackOrderItem, DeliveryOrder, DeliveryOrderItem, DeliveryOrderReturn, DeliveryOrderReturnItem, IncomingProduct, IncomingProductItem, ReturnIncomingProduct, ReturnIncomingProductItem, Scrap, ScrapItem, StockAdjustment, StockAdjustmentItem, StockMove
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender=IncomingProduct)
def create_incoming_product_stock_move(sender, instance, created, **kwargs):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.incoming_product_id,
            destination_location=instance.destination_location,
            move_type='IN'
        ).exists():
            print(f"The Stock Move of this source document {instance.incoming_product_id} and move type of IN already exists")
            return  

    """Create stock move when an incoming inventory record item is validated"""
    if instance.status == "validated":
        items = IncomingProductItem.objects.filter(incoming_product_id=instance.incoming_product_id)
        for item in items:
            stock_move = StockMove(
                product=item.product,
                unit_of_measure=item.product.unit_of_measure,
                quantity=item.quantity_received,
                move_type='IN',
                source_document_id=item.incoming_product_id, 
                source_location=instance.source_location,
                destination_location=instance.destination_location,
                date_created=timezone.now(),
                date_moved=timezone.now(),
            )
            stock_move.save()


@receiver(post_save, sender=DeliveryOrder)
def create_delivery_order_stock_move(sender, instance, created, **kwargs):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.order_unique_id,
            delivery_address=instance.delivery_address,
            move_type='OUT'
        ).exists():
            print(f"The Stock Move of this source document {instance.order_unique_id} and move type of OUT already exists")
            return  

    """Create stock move when a delivery order record item is done"""
    if instance.status == "done":
        items = DeliveryOrderItem.objects.filter(delivery_order_id=instance.id)
        for item in items:
            stock_move = StockMove(
                product=item.product_item,
                unit_of_measure=item.product_item.unit_of_measure,
                quantity=item.quantity_to_deliver,
                move_type='OUT',
                source_document_id=instance.order_unique_id, 
                source_location=instance.source_location,
                delivery_address=instance.delivery_address,
                date_created=timezone.now(),
                date_moved=timezone.now(),
            )
            stock_move.save()



"""This is a different scenario of the signals. It had to be explicitly called in the serializers where it needed to be triggered"""
def create_delivery_order_returns_stock_move(instance):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.unique_record_id,
            destination_location=instance.return_warehouse_location,
            move_type='RETURN'
        ).exists():
            print(f"The Stock Move of this source document {instance.unique_record_id} and move type of RETURN already exists")
            return  

    """Create stock move when a delivery order returns record item is done"""
    items = DeliveryOrderReturnItem.objects.filter(delivery_order_return_id=instance.id)
    for item in items:
        stock_move = StockMove(
            product=item.returned_product_item,
            unit_of_measure=item.returned_product_item.unit_of_measure,
            quantity=item.returned_quantity,
            move_type='RETURN',
            source_document_id=instance.unique_record_id, 
            source_address=instance.source_location,  # Here, instance.source_location is a text field, so we mapped it to source_Address which is a text field too
            destination_location=instance.return_warehouse_location,
            date_created=timezone.now(),
            date_moved=timezone.now(),
        )
        stock_move.save()



@receiver(post_save, sender=ReturnIncomingProduct)
def return_incoming_product_stock_move(sender, instance, created, **kwargs):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.unique_id,
            destination_location=instance.source_document.source_location,  #For the Return, the destination location of the return becomes the source location of the source document
            move_type='RETURN'
        ).exists():
            print(f"The Stock Move of this source document {instance.unique_id} and move type of RETURN already exists")
            return  

    """Create stock move when a return on incoming product record item is done"""
    if instance.is_approved == True:
        items = ReturnIncomingProductItem.objects.filter(return_incoming_product=instance)
        for item in items:
            stock_move = StockMove(
                product=item.product,
                unit_of_measure=item.product.unit_of_measure,
                quantity=item.quantity_to_be_returned,
                move_type='RETURN',
                source_document_id=instance.unique_id, 
                source_location=instance.source_document.destination_location, #The inversion in SOURCE AND DESTINATION was because the source location for the Return has to be the destination location of the soirce document
                destination_location=instance.source_document.source_location,
                date_created=timezone.now(),
                date_moved=timezone.now(),
            )
            stock_move.save()


@receiver(post_save, sender=Scrap)
def scrap_stock_move(sender, instance, created, **kwargs):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.id,
            source_location=instance.warehouse_location,  #For the Return, the destination location of the return becomes the source location of the source document
            move_type='SCRAP'
        ).exists():
            print(f"The Stock Move of this source document {instance.id} and move type of SCRAP already exists")
            return  

    """Create stock move when a Scrap is done"""
    if instance.status == "done":
        items = ScrapItem.objects.filter(scrap=instance)
        for item in items:
            stock_move = StockMove(
                product=item.product,
                unit_of_measure=item.product.unit_of_measure,
                quantity=item.scrap_quantity,
                move_type='SCRAP',
                source_document_id=instance.id, 
                source_location=instance.warehouse_location, 
                date_moved=timezone.now(),
            )
            stock_move.save()



@receiver(post_save, sender=StockAdjustment)
def stock_adjustment_stock_move(sender, instance, created, **kwargs):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.id,
            source_location=instance.warehouse_location,  #For the Return, the destination location of the return becomes the source location of the source document
            move_type='SCRAP'
        ).exists():
            print(f"The Stock Move of this source document {instance.id} and move type of SCRAP already exists")
            return  

    """Create stock move when a Stock Adjustment is done"""
    if instance.status == "done":
        items = StockAdjustmentItem.objects.filter(stock_adjustment=instance)
        for item in items:
            stock_move = StockMove(
                product=item.product,
                unit_of_measure=item.product.unit_of_measure,
                quantity=item.adjusted_quantity,
                move_type='ADJUSTMENT',
                source_document_id=instance.id, 
                source_location=instance.warehouse_location, 
                date_created=timezone.now(),
                date_moved=timezone.now(),
            )
            stock_move.save()


@receiver(post_save, sender=BackOrder)
def back_order_stock_move(sender, instance, created, **kwargs):
    """First make a check to know if this record does not exists so as to prevent unnecessary duplications"""
    if StockMove.objects.filter(
            source_document_id=instance.id,
            source_location=instance.source_location,  #For the Return, the destination location of the return becomes the source location of the source document
            move_type='BACKORDER'
        ).exists():
            print(f"The Stock Move of this source document {instance.id} and move type of BACKORDER already exists")
            return  

    """Create stock move when a Back Order is done"""
    if instance.status == "done":
        items = BackOrderItem.objects.filter(back_order=instance)
        for item in items:
            stock_move = StockMove(
                product=item.product,
                unit_of_measure=item.product.unit_of_measure,
                quantity=item.expected_quantity - item.quantity_received,
                move_type='BACKORDER',
                source_document_id=instance.id, 
                source_location=instance.destination_location, 
                destination_location=instance.source_location, 
                date_created=timezone.now(),
                date_moved=timezone.now(),
            )
            stock_move.save()