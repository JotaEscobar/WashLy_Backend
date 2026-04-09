import uuid
from django.db import migrations

def gen_uuid(apps, schema_editor):
    Ticket = apps.get_model('tickets', 'Ticket')
    for row in Ticket.objects.all():
        row.tracking_uuid = uuid.uuid4()
        row.save(update_fields=['tracking_uuid'])

class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0002_ticket_tracking_uuid'),
    ]

    operations = [
        migrations.RunPython(gen_uuid, reverse_code=migrations.RunPython.noop),
    ]
