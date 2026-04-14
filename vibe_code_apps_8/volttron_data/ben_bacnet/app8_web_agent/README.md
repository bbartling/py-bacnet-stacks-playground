# app8_web_agent

VOLTTRON web-enabled BAS Lite agent for App 8 modular runtime.

- Serves static React build under `/app8/`
- Exposes `/app8/api/*` JSON endpoints used by the App 8 frontend
- Subscribes to `devices/<device>/all` topics from Platform Driver

This package is intentionally self-contained so Dockerized VOLTTRON can install it directly.
