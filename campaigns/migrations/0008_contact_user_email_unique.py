from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('campaigns', '0007_emaillog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contact',
            name='email',
            field=models.EmailField(),
        ),
        migrations.AlterUniqueTogether(
            name='contact',
            unique_together={('user', 'email')},
        ),
    ]
