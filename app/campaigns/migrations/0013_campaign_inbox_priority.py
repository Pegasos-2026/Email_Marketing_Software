from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0012_alter_contact_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='campaign',
            name='inbox_priority',
            field=models.BooleanField(
                default=True,
                help_text='When enabled, send a personalized plain-style email optimized for Gmail Primary inbox.',
            ),
        ),
    ]
