# Generated manually

from django.db import migrations, models


def set_initial_display_order(apps, schema_editor):
    Location = apps.get_model('reservations', 'Location')
    for i, loc in enumerate(Location.objects.all().order_by('name')):
        loc.display_order = i * 10
        loc.save(update_fields=['display_order'])


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0012_visit_record'),
    ]

    operations = [
        migrations.AddField(
            model_name='location',
            name='display_order',
            field=models.PositiveIntegerField(
                default=0,
                help_text='数値が小さいほど予約画面などで先に表示されます。',
                verbose_name='表示順',
            ),
        ),
        migrations.AlterModelOptions(
            name='location',
            options={
                'ordering': ['display_order', 'name'],
                'verbose_name': '場所',
                'verbose_name_plural': '場所',
            },
        ),
        migrations.RunPython(set_initial_display_order, migrations.RunPython.noop),
    ]
