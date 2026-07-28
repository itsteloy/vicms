from vicdashboard.models import DeliveryReceiptLine
print('total rows:', DeliveryReceiptLine.objects.count())
for line in DeliveryReceiptLine.objects.all():
    print(line.id, line.description, line.quantity)

