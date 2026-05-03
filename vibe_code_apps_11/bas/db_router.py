"""Database router directing time series models to a dedicated database.

This router routes the ``TimeSeriesData`` model to the ``timeseries``
database when reading and writing. All other models remain on the
``default`` database. By default Django sends migration operations to all
configured databases. Here we ensure that migrations for the time series
table run on the ``timeseries`` database, while everything else stays on
``default``.

If the ``timeseries`` database is not defined in settings.DATABASES,
operations will fall back to the default database implicitly.
"""

from typing import Optional


class TimeSeriesRouter:
    """Route the TimeSeriesData model to the ``timeseries`` database."""

    def _is_timeseries_model(self, model) -> bool:
        return model._meta.db_table == 'bas_timeseries_data'

    def db_for_read(self, model, **hints) -> Optional[str]:
        if self._is_timeseries_model(model):
            return 'timeseries'
        return None

    def db_for_write(self, model, **hints) -> Optional[str]:
        if self._is_timeseries_model(model):
            return 'timeseries'
        return None

    def allow_relation(self, obj1, obj2, **hints) -> Optional[bool]:
        # Allow relations if neither object is timeseries or both are timeseries
        if self._is_timeseries_model(obj1.__class__) or self._is_timeseries_model(obj2.__class__):
            return True
        return None

    def allow_migrate(self, db: str, app_label: str, model_name: Optional[str] = None, **hints) -> Optional[bool]:
        if model_name == 'timeseriesdata':
            return db == 'timeseries'
        # Migrate all other bas models on the default DB
        return db == 'default'