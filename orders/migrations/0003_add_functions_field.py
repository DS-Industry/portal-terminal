# Generated manually for adding functions field to Program model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0002_vendotekserverconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='functions',
            field=models.CharField(
                blank=True,
                help_text='Функции программы (через запятую)',
                max_length=500,
                null=True
            ),
        ),
    ]


