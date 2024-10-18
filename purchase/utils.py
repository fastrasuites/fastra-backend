from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import HttpResponse


def generate_model_pdf(model):
    # Create the HttpResponse object with PDF headers
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{model._meta.verbose_name}_{model.id}.pdf"'

    # Create the PDF object, using the response object as the "file."
    p = canvas.Canvas(response, pagesize=letter)

    # Write content to the PDF
    p.drawString(100, 750, f"{model._meta.verbose_name}: {model.id}")
    p.drawString(100, 725, f"Date Created: {model.date_created.strftime('%Y-%m-%d')}")
    if model.expiry_date:
        p.drawString(100, 700,
                     f"Deadline Date: {model.expiry_date.strftime('%Y-%m-%d') if model.expiry_date else 'None'}")
    p.drawString(100, 675, f"Vendor: {model.vendor.company_name}")
    p.drawString(100, 650, f"Status: {model.status}")

    # List RFQ items
    y_position = 600
    p.drawString(100, y_position, "Products:")
    for item in model.items.all():
        y_position -= 25
        p.drawString(100, y_position, f"- {item.product.product_name}, Qty: {item.qty}")

    # Close the PDF object and finish
    p.showPage()
    p.save()

    return response
