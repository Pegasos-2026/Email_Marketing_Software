from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emails', '0004_alter_emailsetting_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='emailsetting',
            name='provider',
            field=models.CharField(choices=[('SendGrid', 'SendGrid'), ('SMTP', 'SMTP')], default='SMTP', max_length=50),
        ),
        migrations.AlterField(
            model_name='emailsetting',
            name='api_key',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='emailsetting',
            name='from_email',
            field=models.EmailField(blank=True, null=True, max_length=254),
        ),
        migrations.AlterField(
            model_name='emailsetting',
            name='from_name',
            field=models.CharField(blank=True, null=True, max_length=100),
        ),
        migrations.AddField(
            model_name='emailsetting',
            name='smtp_host',
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='emailsetting',
            name='smtp_port',
            field=models.PositiveIntegerField(default=587),
        ),
        migrations.AddField(
            model_name='emailsetting',
            name='smtp_user',
            field=models.CharField(blank=True, null=True, max_length=255),
        ),
        migrations.AddField(
            model_name='emailsetting',
            name='smtp_password',
            field=models.TextField(blank=True, null=True),
        ),
    ]
