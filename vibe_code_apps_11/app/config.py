from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_title: str = os.environ.get('DIY_BAS_APP_TITLE', 'diy-bas supervisor')
    site_name: str = os.environ.get('DIY_BAS_SITE_NAME', 'Test Bench')
    diy_bacnet_url: str = os.environ.get('DIY_BACNET_URL', 'http://127.0.0.1:8080').rstrip('/')
    diy_schedule_object_name: str = os.environ.get('DIY_SCHEDULE_OBJECT_NAME', 'occupancy-schedule')
    bacnet_rpc_api_key: str = os.environ.get('BACNET_RPC_API_KEY', '').strip()
    rpc_timeout: float = float(os.environ.get('DIY_RPC_TIMEOUT', '15'))
    bind: str = os.environ.get('BIND', '0.0.0.0')
    port: int = int(os.environ.get('PORT', '5050'))
    debug: bool = os.environ.get('DJANGO_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    data_dir: Path = Path(os.environ.get('DIY_BAS_DATA_DIR', str(BASE_DIR / 'data'))).resolve()
    webroot: Path = Path(os.environ.get('DIY_BAS_WEBROOT', str(BASE_DIR / 'frontend'))).resolve()
    trend_retention_days: int = int(os.environ.get('DIY_BAS_TREND_RETENTION_DAYS', '30'))
    default_poll_interval: int = int(os.environ.get('DIY_BAS_DEFAULT_POLL_INTERVAL', '30'))
    min_poll_interval: int = int(os.environ.get('DIY_BAS_MIN_POLL_INTERVAL', '5'))
    max_poll_interval: int = int(os.environ.get('DIY_BAS_MAX_POLL_INTERVAL', '900'))
    default_whois_start: int = int(os.environ.get('DIY_BAS_WHOIS_START_INSTANCE', '1'))
    default_whois_end: int = int(os.environ.get('DIY_BAS_WHOIS_END_INSTANCE', '4194303'))
    bacnet_gateway_instance: int = int(os.environ.get('DIY_BACNET_SERVER_INSTANCE', '123456'))
    hide_gateway_device: bool = os.environ.get('DIY_BAS_HIDE_GATEWAY_DEVICE', 'true').lower() in ('1', 'true', 'yes')
    shared_outside_air_point: str = os.environ.get('DIY_BAS_SHARED_OAT_POINT', '').strip()
    audit_retention_days: int = int(os.environ.get('DIY_BAS_AUDIT_RETENTION_DAYS', '30'))
    alarm_event_retention_days: int = int(os.environ.get('DIY_BAS_ALARM_EVENT_RETENTION_DAYS', '90'))
    session_hours: int = max(1, int(os.environ.get('DIY_BAS_SESSION_HOURS', '24')))
    # ntfy.sh (or self-hosted) push — POST body = message, headers Title / Priority / Tags
    # DIY_BAS_NTFY_ALLOWED is the primary switch; if unset, DIY_BAS_NTFY_ENABLED is still honored.
    ntfy_allowed: bool = (
        os.environ.get('DIY_BAS_NTFY_ALLOWED', 'false').lower() in ('1', 'true', 'yes')
        if 'DIY_BAS_NTFY_ALLOWED' in os.environ
        else os.environ.get('DIY_BAS_NTFY_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    )
    ntfy_url: str = (os.environ.get('DIY_BAS_NTFY_URL', 'https://ntfy.sh') or 'https://ntfy.sh').rstrip('/')
    ntfy_topic: str = os.environ.get('DIY_BAS_NTFY_TOPIC', '').strip()
    ntfy_username: str = os.environ.get('DIY_BAS_NTFY_USERNAME', '').strip()
    ntfy_password: str = os.environ.get('DIY_BAS_NTFY_PASSWORD', '')
    ntfy_timeout_sec: float = float(os.environ.get('DIY_BAS_NTFY_TIMEOUT_SEC', '20') or '20')


settings = Settings()
