import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0008_tag_category_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opentracking',
            name='campaign_recipient',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='open_tracking',
                to='campaigns.campaignrecipient',
            ),
        ),
        migrations.AddField(
            model_name='opentracking',
            name='drip_enrollment',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='open_trackings',
                to='campaigns.dripenrollment',
            ),
        ),
        migrations.AddField(
            model_name='opentracking',
            name='drip_step',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='open_trackings',
                to='campaigns.dripstep',
            ),
        ),
    ]
