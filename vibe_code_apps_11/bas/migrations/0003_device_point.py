from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Add BACnet Device and Point models.

    These models are optional and are used to persist metadata about
    discovered devices and points in the Django database. They mirror the
    structure of the Niagara framework by storing device instances and
    priority arrays. The initial migration creates the tables and sets up
    a foreign key relationship from points to devices.
    """

    dependencies = [
        ('bas', '0002_userprofile_phone_number'),
    ]

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('device_instance', models.PositiveIntegerField(unique=True)),
                ('address', models.CharField(blank=True, default='', max_length=255)),
                ('label', models.CharField(blank=True, default='', max_length=255)),
                ('status', models.CharField(blank=True, default='online', max_length=64)),
                ('offline', models.BooleanField(default=False)),
                ('last_discovered', models.DateTimeField(blank=True, null=True)),
                ('note', models.TextField(blank=True, default='')),
            ],
            options={
                'db_table': 'bas_device',
                'verbose_name': 'BACnet device',
                'verbose_name_plural': 'BACnet devices',
            },
        ),
        migrations.CreateModel(
            name='Point',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('point_id', models.CharField(max_length=128, unique=True)),
                ('object_identifier', models.CharField(max_length=64)),
                ('property_identifier', models.CharField(default='present-value', max_length=64)),
                ('label', models.CharField(blank=True, default='', max_length=255)),
                ('units', models.CharField(blank=True, default='', max_length=64)),
                ('commandable', models.BooleanField(default=False)),
                ('value', models.CharField(blank=True, default='', max_length=255)),
                ('value_state', models.CharField(blank=True, default='fresh', max_length=32)),
                ('in_alarm', models.BooleanField(default=False)),
                ('device_offline_alarm', models.BooleanField(default=False)),
                ('priority_array', models.JSONField(blank=True, default=dict)),
                ('last_updated', models.DateTimeField(blank=True, null=True)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='points', to='bas.device')),
            ],
            options={
                'db_table': 'bas_point',
                'verbose_name': 'BACnet point',
                'verbose_name_plural': 'BACnet points',
            },
        ),
    ]