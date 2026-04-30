from django.apps import AppConfig


class BasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bas'

    def ready(self) -> None:
        import bas.signals  # noqa: F401
