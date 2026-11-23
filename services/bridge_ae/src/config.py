"""Configuration settings loaded from environment variables for the Bridge AE."""

import os
from dataclasses import dataclass, field


@dataclass
class BridgeConfig:
    """Configuration parameters governing data health classification and storage."""
    
    influxdb_url: str = field(default_factory=lambda: os.getenv("INFLUXDB_URL", "http://influxdb:8086"))
    influxdb_token: str = field(default_factory=lambda: os.getenv("INFLUXDB_TOKEN", ""))
    influxdb_org: str = field(default_factory=lambda: os.getenv("INFLUXDB_ORG", "fhtw_aiot"))
    influxdb_bucket: str = field(default_factory=lambda: os.getenv("INFLUXDB_BUCKET", "cabin_telemetry"))
    
    max_latency_s: float = field(default_factory=lambda: float(os.getenv("MAX_LATENCY_S", "2.5")))
    max_stale_s: float = field(default_factory=lambda: float(os.getenv("MAX_STALE_S", "10.0")))
    max_delta_t_c: float = field(default_factory=lambda: float(os.getenv("MAX_DELTA_T_C", "1.5")))
    
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "5000")))

    # Closed-loop HVAC rule dispatch (set BRIDGE_CLOSED_LOOP_ENABLED=false to revert to ACMEScripts-only)
    closed_loop_enabled: bool = field(
        default_factory=lambda: os.getenv("BRIDGE_CLOSED_LOOP_ENABLED", "true").lower() in ("true", "1", "yes")
    )
    closed_loop_refresh_s: float = field(default_factory=lambda: float(os.getenv("BRIDGE_CLOSED_LOOP_REFRESH_S", "2.0")))
    onem2m_cse_url: str = field(default_factory=lambda: os.getenv("ONEM2M_CSE_URL", "http://onem2m_cse:8080/sdv-cse"))
    onem2m_admin_origin: str = field(default_factory=lambda: os.getenv("ONEM2M_ADMIN_ORIGIN", "CAdmin"))


config = BridgeConfig()

