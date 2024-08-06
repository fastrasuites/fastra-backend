# from django import forms
# from .models import PurchaseRequest, PurchaseRequestItem, Department, Vendor

# class PurchaseRequestForm(forms.ModelForm):
#     class Meta:
#         model = PurchaseRequest
#         fields = ['id', 'date', 'department', 'status', 'purpose', 'suggested_vendor']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['department'].queryset = Department.objects.all()
#         self.fields['suggested_vendor'].queryset = Vendor.objects.all()

# class PurchaseRequestItemForm(forms.ModelForm):
#     class Meta:
#         model = PurchaseRequestItem
#         fields = ['product_name', 'description', 'qty', 'estimated_unit_price', 'total_price']

# PurchaseRequestItemFormSet = forms.inlineformset_factory(
#     PurchaseRequest,
#     PurchaseRequestItem,
#     form=PurchaseRequestItemForm,
#     extra=1,
#     can_delete=True
# )