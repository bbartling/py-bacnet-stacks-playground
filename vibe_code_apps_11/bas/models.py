from django.conf import settings
from django.db import models

from app.roles import ROLE_INTEGRATOR, ROLE_OPERATOR


class BasRole(models.TextChoices):
    """BAS-style roles stored on the profile (Django User holds credentials)."""

    INTEGRATOR = ROLE_INTEGRATOR, 'System integrator'
    MAINTENANCE = 'maintenance', 'Maintenance'
    OPERATOR = ROLE_OPERATOR, 'Building operator'


class UserProfile(models.Model):
    """Per-user BAS flags; integrator from env is also is_superuser on User."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bas_profile')
    bas_role = models.CharField(max_length=64, choices=BasRole.choices, default=BasRole.OPERATOR)
    read_only = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)
    # Optional phone number for contacting users. Not required for login.
    phone_number = models.CharField(max_length=20, blank=True, default="")

    class Meta:
        db_table = 'bas_userprofile'

    def __str__(self) -> str:
        return f'{self.user.username} ({self.bas_role})'


# ---------------------------------------------------------------------------
# BACnet Devices and Points
#
# While the diy-bas project historically stores discovered devices and points in
# JSON files under ``data/`` and merges live values from the diy-bacnet server
# on demand, we define optional Django models to persist device and point
# metadata within the relational database. These models emulate the Niagara
# framework’s schema: a Device contains many Points and each Point maintains
# a BACnet priority array as JSON along with alarm/override flags. Using
# Django’s admin you can view and edit devices and points, and tests can
# interact with these models without requiring the external JSON stores.

class Device(models.Model):
    """BACnet device discovered on the network.

    * ``device_instance`` – the BACnet device instance number; must be unique.
    * ``address`` – human‑readable address (e.g. IP:port) if known.
    * ``label`` – optional label/name for the device.
    * ``status`` – operational status (e.g. ``online``, ``offline``, ``fault``).
    * ``offline`` – flag indicating whether the device is currently offline.
    * ``last_discovered`` – timestamp of the last successful discovery/poll.
    * ``note`` – freeform note for integrators to annotate devices.
    """

    device_instance = models.PositiveIntegerField(unique=True)
    address = models.CharField(max_length=255, blank=True, default='')
    label = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=64, blank=True, default='online')
    offline = models.BooleanField(default=False)
    last_discovered = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'bas_device'
        verbose_name = 'BACnet device'
        verbose_name_plural = 'BACnet devices'

    def __str__(self) -> str:
        return self.label or f'Device {self.device_instance}'


class Point(models.Model):
    """BACnet point exposed by a Device.

    This model stores metadata about BACnet points similar to how Niagara
    represents a ControlPoint. It is not strictly required for diy‑bas but
    provides a convenient relational schema for tests and future extensions.

    * ``device`` – owning Device
    * ``point_id`` – unique identifier used by diy‑bas; string to allow UUIDs
    * ``object_identifier`` – BACnet object identifier (e.g. ``analogValue:1``)
    * ``property_identifier`` – BACnet property identifier (usually
      ``present-value``)
    * ``label`` – user‑friendly name
    * ``units`` – engineering units
    * ``commandable`` – whether the point is commandable (has a writable
      property)
    * ``value`` – latest value as a string (raw value stored separately in
      ``latest_values.json``)
    * ``value_state`` – ``fresh`` or ``stale`` indicating poll freshness
    * ``in_alarm`` – flag set when this point is in alarm
    * ``device_offline_alarm`` – flag set when the point’s device is offline
    * ``priority_array`` – JSON field storing BACnet priority array; keys are
      integers 1–16 mapping to values or null
    * ``last_updated`` – timestamp of last value update
    """

    device = models.ForeignKey('bas.Device', related_name='points', on_delete=models.CASCADE)
    point_id = models.CharField(max_length=128, unique=True)
    object_identifier = models.CharField(max_length=64)
    property_identifier = models.CharField(max_length=64, default='present-value')
    label = models.CharField(max_length=255, blank=True, default='')
    units = models.CharField(max_length=64, blank=True, default='')
    commandable = models.BooleanField(default=False)
    value = models.CharField(max_length=255, blank=True, default='')
    value_state = models.CharField(max_length=32, blank=True, default='fresh')
    in_alarm = models.BooleanField(default=False)
    device_offline_alarm = models.BooleanField(default=False)
    # Additional point status flags mirroring Niagara control point states.
    # ``disabled``: the point has been disabled and should not be polled or commanded.
    disabled = models.BooleanField(default=False)
    # ``overridden``: indicates a manual override of the point’s value via BACnet priority array.
    overridden = models.BooleanField(default=False)
    # ``fault``: a fault state often relates to configuration errors or failed communication.
    fault = models.BooleanField(default=False)
    priority_array = models.JSONField(blank=True, default=dict)
    last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bas_point'
        verbose_name = 'BACnet point'
        verbose_name_plural = 'BACnet points'

    def __str__(self) -> str:
        return self.label or self.point_id


# ---------------------------------------------------------------------------
# Time series data model
#
# The diy‑bas system records a high volume of telemetry from BACnet points.
# Storing this data in the same SQLite database used for user accounts and
# configuration would quickly exhaust the concurrency and performance limits
# of SQLite in production. To support time series workloads, we define a
# ``TimeSeriesData`` model that can be routed to a separate TimescaleDB (or
# PostgreSQL) database via a custom database router. Each row represents a
# single sensor reading for a point at a specific timestamp along with an
# optional status flag. When configuring Django, a second database entry
# called ``timeseries`` should point at the Timescale/PostgreSQL instance and
# the router will ensure that reads and writes for this model are directed
# there. If the ``timeseries`` database is not configured, Django will fall
# back to the default database.

class TimeSeriesData(models.Model):
    """Telemetry sample for a BACnet point.

    * ``point`` – reference to the point that produced this reading.
    * ``timestamp`` – when the value was recorded (UTC).
    * ``value`` – numeric value recorded. If non‑numeric values are needed
      (e.g. strings or booleans) this field may be changed to JSONField.
    * ``status`` – optional short code indicating the quality of the
      measurement (e.g. ``ok``, ``stale``, ``fault``).
    """

    point = models.ForeignKey('bas.Point', related_name='timeseries', on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    value = models.FloatField()
    status = models.CharField(max_length=32, default='ok', blank=True)

    class Meta:
        db_table = 'bas_timeseries_data'
        verbose_name = 'Time series data'
        verbose_name_plural = 'Time series data'

    def __str__(self) -> str:
        # Represent the sample as "pointId at timestamp: value". If the related
        # point is not loaded, fall back to the primary key.
        try:
            return f"{self.point.point_id} at {self.timestamp}: {self.value}"
        except Exception:
            return f"{self.pk} at {self.timestamp}: {self.value}"


class AuditLog(models.Model):
    """Read-only mirror of legacy SQLite audit table (trend DB)."""

    ts = models.BigIntegerField()
    username = models.CharField(max_length=255)
    role = models.CharField(max_length=64)
    action = models.CharField(max_length=255)
    success = models.IntegerField(default=1)
    details_json = models.TextField(default='{}')

    class Meta:
        db_table = 'audit_logs'
        managed = False
