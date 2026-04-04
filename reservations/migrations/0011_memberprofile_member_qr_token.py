import uuid

from django.db import migrations, models


def fill_member_qr_tokens(apps, schema_editor):
    MemberProfile = apps.get_model('reservations', 'MemberProfile')
    for row in MemberProfile.objects.all():
        row.member_qr_token = uuid.uuid4()
        row.save(update_fields=['member_qr_token'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0010_reservation_customer_phone_optional'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberprofile',
            name='member_qr_token',
            field=models.UUIDField(editable=False, null=True, verbose_name='会員QR用トークン'),
        ),
        migrations.RunPython(fill_member_qr_tokens, noop),
        migrations.AlterField(
            model_name='memberprofile',
            name='member_qr_token',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
                verbose_name='会員QR用トークン',
            ),
        ),
    ]
