from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """Add Point status flags and time series data model.

    This migration extends the ``Point`` model with three boolean status
    fields—``disabled``, ``overridden`` and ``fault``—that mirror Niagara
    control point states. It also introduces the ``TimeSeriesData`` model for
    persisting high‑frequency telemetry into a separate database (e.g.
    TimescaleDB). The router should be configured to direct this model to
    the ``timeseries`` database. If a second database is not configured,
    data will fall back to the default database.
    """

    dependencies = [
        ('bas', '0003_device_point'),
    ]

    operations = [
        # Extend Point model with status flags
        migrations.AddField(
            model_name='point',
            name='disabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='point',
            name='overridden',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='point',
            name='fault',
            field=models.BooleanField(default=False),
        ),
        # Create TimeSeriesData model
        migrations.CreateModel(
            name='TimeSeriesData',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField()),
                ('value', models.FloatField()),
                ('status', models.CharField(blank=True, default='ok', max_length=32)),
                ('point', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='timeseries', to='bas.point')),
            ],
            options={
                'db_table': 'bas_timeseries_data',
                'verbose_name': 'Time series data',
                'verbose_name_plural': 'Time series data',
            },
        ),
    ]