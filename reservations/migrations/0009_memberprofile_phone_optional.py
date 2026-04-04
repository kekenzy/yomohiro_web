# Generated manually for optional MemberProfile.phone

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0008_add_is_special_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='memberprofile',
            name='phone',
            field=models.CharField(
                blank=True,
                default='',
                max_length=15,
                validators=[
                    django.core.validators.RegexValidator(
                        message='電話番号は数字、ハイフン、括弧、スペースのみ使用可能です',
                        regex='^$|^[\d\\-\\(\\)\\s]+$',
                    )
                ],
                verbose_name='電話番号',
            ),
        ),
    ]
