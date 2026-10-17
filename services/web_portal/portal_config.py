"""Configuration parameters for the public-facing Web portal."""

import os
from dataclasses import dataclass, field


@dataclass
class WebPortalConfig:
    """Runtime configuration loaded from environment variables."""

    host: str = field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    debug: bool = field(default_factory=lambda: os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes"))
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", "sdv-dev-portal-secret-key"))
    onem2m_cse_url: str = field(default_factory=lambda: os.getenv("ONEM2M_CSE_URL", "http://onem2m_cse:8080/sdv-cse"))
    onem2m_fallback_url: str = field(default_factory=lambda: os.getenv("ONEM2M_FALLBACK_URL", "http://localhost:8080/sdv-cse"))
    onem2m_admin_origin: str = field(default_factory=lambda: os.getenv("ONEM2M_ADMIN_ORIGIN", "CAdmin"))
    onem2m_rvi: str = field(default_factory=lambda: os.getenv("ONEM2M_RVI", "3"))
    influxdb_url: str = field(default_factory=lambda: os.getenv("INFLUXDB_URL", "http://influxdb:8086"))
    influxdb_token: str = field(default_factory=lambda: os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN", "ChangeThisToAStrongGeneratedSecretToken=="))
    influxdb_org: str = field(default_factory=lambda: os.getenv("DOCKER_INFLUXDB_INIT_ORG", "fhtw_aiot"))
    influxdb_bucket: str = field(default_factory=lambda: os.getenv("DOCKER_INFLUXDB_INIT_BUCKET", "cabin_telemetry"))

    def get_effective_onem2m_url(self) -> str:
        """
        Returns the reachable oneM2M CSEBase URL.

        If the primary URL (e.g. Docker network DNS 'onem2m_cse') is unresolvable,
        falls back to localhost for local host-level development and testing.
        """
        import socket
        from urllib.parse import urlparse

        primary = self.onem2m_cse_url
        try:
            parsed = urlparse(primary)
            host = parsed.hostname
            if host and host not in ("localhost", "127.0.0.1"):
                socket.gethostbyname(host)
            return primary
        except (socket.gaierror, Exception):
            return self.onem2m_fallback_url


config = WebPortalConfig()

