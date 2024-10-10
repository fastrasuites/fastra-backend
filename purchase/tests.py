from django.test import TestCase

# Create your tests here.
from django.test import TestCase
from.models import RequestForQuotation, RequestForQuotationItem, Product, Vendor
from.views import add_rfq_total_price
from django.urls import reverse
from django.contrib.auth.models import User

class TestAddRFQTotalPrice(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product = Product.objects.create(name='Test Product')
        self.vendor = Vendor.objects.create(name='Test Vendor', category='test category')
        self.rfq = RequestForQuotation.objects.create(formatted_id='RFQ00001', vendor=self.vendor, requester=self.user)
        self.rfq_item = RequestForQuotationItem.objects.create(request_for_quotation=self.rfq,
                                                               product=self.product, qty=2, estimated_unit_price=100)

    def test_add_rfq_total_price_prints_correct_total_price(self):
        response = self.client.get(reverse('add_rfq_total_price', kwargs={'formatted_id': self.rfq.formatted_id}))
        self.assertEqual(response.context['rfq_total_price'], 200)

    def test_add_rfq_total_price_prints_correct_rfq_object(self):
        response = self.client.get(reverse('add_rfq_total_price', kwargs={'formatted_id': self.rfq.formatted_id}))
        self.assertEqual(response.context['rfq'], self.rfq)

    def test_add_rfq_total_price_renders_correct_template(self):
        response = self.client.get(reverse('add_rfq_total_price', kwargs={'formatted_id': self.rfq.formatted_id}))
        self.assertTemplateUsed(response, 'purchase/create_rfq.html')

    def test_add_rfq_total_price_with_nonexistent_rfq_id_returns_404(self):
        response = self.client.get(reverse('add_rfq_total_price', kwargs={'formatted_id': 999}))
        self.assertEqual(response.status_code, 404)

    def test_add_rfq_total_price_with_logged_out_user_redirects_to_login(self):
        self.client.logout()
        response = self.client.get(reverse('add_rfq_total_price', kwargs={'formatted_id': self.rfq.id}))
        self.assertRedirects(response, '/accounts/login/?next=/add')

class RFQTotalPriceTestCase(TestCase):
    def setUp(self):
        # Create a product
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.product_one = Product.objects.create(name='Test Product_one')
        self.product_two = Product.objects.create(name='Test Product_two')
        self.vendor = Vendor.objects.create(name='Test Vendor', category='test category')

        # Create a RFQ
        self.rfq = RequestForQuotation.objects.create(formatted_id='RFQ00001', vendor=self.vendor, requester=self.user)

        # Create RFQ items
        RequestForQuotationItem.objects.create(request_for_quotation=self.rfq,
                                               product=self.product_one, qty=2, estimated_unit_price=50)
        RequestForQuotationItem.objects.create(request_for_quotation=self.rfq,
                                               product=self.product_two, qty=3, estimated_unit_price=75)

    def test_rfq_total_price_is_correctly_updated(self):
        rfq = RequestForQuotation.objects.get(subject='Test RFQ')
        self.assertEqual(rfq.rfq_total_price, 325)  # 2*50 + 3*75

    def test_rfq_total_price_is_updated_when_item_quantity_changes(self):
        rfq = RequestForQuotation.objects.get(formatted_id='RFQ00001', vendor=self.vendor)
        item = RequestForQuotationItem.objects.get(request_for_quotation=rfq, product__name='Test Product_one')
        item.qty = 4
        item.save()
        self.assertEqual(rfq.rfq_total_price, 425)  # 4*50 + 3*75

    def test_rfq_total_price_is_updated_when_item_price_changes(self):
        rfq = RequestForQuotation.objects.get(formatted_id='RFQ00001', vendor=self.vendor)
        item = RequestForQuotationItem.objects.get(request_for_quotation=rfq, product__name='Test Product_one')
        item.price = 60
        item.save()
        self.assertEqual(rfq.rfq_total_price, 240)  # 2*60 + 3*75

    def test_rfq_total_price_is_updated_when_new_item_is_added(self):
        rfq = RequestForQuotation.objects.get(formatted_id='RFQ00001', vendor=self.vendor)
        product = Product.objects.create(name='New Product')
        RequestForQuotationItem.objects.create(request_for_quotation=rfq, product=product,
                                               qty=1, estimated_unit_price=150)
        self.assertEqual(rfq.rfq_total_price, 495)  # 2*60 + 3*75 + 1*150

    def test_rfq_total_price_is_updated_when_item_is_deleted(self):
        rfq = RequestForQuotation.objects.get(formatted_id='RFQ00001', vendor=self.vendor)
        item = RequestForQuotationItem.objects.get(request_for_quotation=rfq, product__name='Test Product_one')
        item.delete()
        self.assertEqual(rfq.rfq_total_price, 375)  # 3*75 + 1*150