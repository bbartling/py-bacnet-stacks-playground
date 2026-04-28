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
    flask_debug: bool = os.environ.get('FLASK_DEBUG', 'false').lower() in ('1', 'true', 'yes')
    data_dir: Path = Path(os.environ.get('DIY_BAS_DATA_DIR', str(BASE_DIR / 'data'))).resolve()
    webroot: Path = Path(os.environ.get('DIY_BAS_WEBROOT', str(BASE_DIR / 'frontend'))).resolve()
    enable_ws_poll: bool = os.environ.get('ENABLE_WS_POLL', 'true').lower() in ('1', 'true', 'yes')
    ws_poll_interval: float = float(os.environ.get('WS_POLL_INTERVAL', '10'))
    trend_retention_days: int = int(os.environ.get('DIY_BAS_TREND_RETENTION_DAYS', '30'))
    poll_flush_seconds: float = float(os.environ.get('DIY_BAS_POLL_FLUSH_SECONDS', '10'))
    poll_batch_size: int = int(os.environ.get('DIY_BAS_POLL_BATCH_SIZE', '50'))
    default_poll_interval: int = int(os.environ.get('DIY_BAS_DEFAULT_POLL_INTERVAL', '30'))
    min_poll_interval: int = int(os.environ.get('DIY_BAS_MIN_POLL_INTERVAL', '5'))
    max_poll_interval: int = int(os.environ.get('DIY_BAS_MAX_POLL_INTERVAL', '900'))
    default_whois_start: int = int(os.environ.get('DIY_BAS_WHOIS_START_INSTANCE', '1'))
    default_whois_end: int = int(os.environ.get('DIY_BAS_WHOIS_END_INSTANCE', '4194303'))
    bacnet_gateway_instance: int = int(os.environ.get('DIY_BACNET_SERVER_INSTANCE', '123456'))
    hide_gateway_device: bool = os.environ.get('DIY_BAS_HIDE_GATEWAY_DEVICE', 'true').lower() in ('1', 'true', 'yes')
    stale_multiplier: float = float(os.environ.get('DIY_BAS_STALE_MULTIPLIER', '2.5'))
    stale_min_seconds: int = int(os.environ.get('DIY_BAS_STALE_MIN_SECONDS', '120'))
    shared_outside_air_point: str = os.environ.get('DIY_BAS_SHARED_OAT_POINT', '').strip()
    latest_values_flush_seconds: int = int(os.environ.get('DIY_BAS_LATEST_VALUES_FLUSH_SECONDS', '300'))
    log_level: str = os.environ.get('DIY_BAS_LOG_LEVEL', 'INFO').upper()
    log_to_file: bool = os.environ.get('DIY_BAS_LOG_TO_FILE', 'false').lower() in ('1', 'true', 'yes')
    log_retention_days: int = int(os.environ.get('DIY_BAS_LOG_RETENTION_DAYS', '30'))
    audit_retention_days: int = int(os.environ.get('DIY_BAS_AUDIT_RETENTION_DAYS', '30'))


settings = Settings()
