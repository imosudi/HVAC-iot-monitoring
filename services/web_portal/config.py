"""Configuration module for the public-facing Flask web portal."""

try:
    from .portal_config import WebPortalConfig, config
except (ImportError, ValueError):
    from portal_config import WebPortalConfig, config

__all__ = ["WebPortalConfig", "config"]
