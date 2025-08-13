# In the generated migration file (something like 0002_add_firebase_uid.py)
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('App', '0001_initial'),  # Replace with your last migration
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='firebase_uid',
            field=models.CharField(blank=True, max_length=128, null=True, unique=True),
        ),
    ]
