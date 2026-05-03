from django.db import migrations, models


class Migration(migrations.Migration):
    """Add phone_number field to UserProfile for contact information."""

    dependencies = [
        ('bas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='phone_number',
            field=models.CharField(default='', blank=True, max_length=20),
        ),
    ]