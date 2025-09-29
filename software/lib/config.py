"""
Unified configuration system for BSides Badge.
Handles loading of WiFi, HomeAssistant, and other settings from config.json.
"""

import json
import os

# Default configuration values
DEFAULT_CONFIG = {
    "wifi": {
        "ssid": "",
        "password": "",
        "url": "",
        "url_qr": ""
    },
    "homeassistant": {
        "enabled": False,
        "broker": "",
        "port": 1883,
        "username": "",
        "password": "",
        "device_name": "BSides Badge",
        "discovery_prefix": "homeassistant"
    },
    "badge": {
        "auto_connect": False,
        "scan_on_startup": False,
        "debug": False
    }
}

class Config:
    """Configuration manager for badge settings."""

    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        """Load configuration from file, creating default if missing."""
        try:
            with open(self.config_file, "r") as f:
                loaded_config = json.load(f)
                # Deep merge with defaults
                self._merge_config(self.config, loaded_config)
                print(f"Configuration loaded from {self.config_file}")
        except OSError:
            print(f"Config file {self.config_file} not found, using defaults")
            self.save()  # Create default config file
        except ValueError as e:
            print(f"Invalid JSON in {self.config_file}: {e}")
            print("Using default configuration")

    def save(self):
        """Save current configuration to file."""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
                print(f"Configuration saved to {self.config_file}")
        except OSError as e:
            print(f"Failed to save config: {e}")

    def _merge_config(self, base, update):
        """Deep merge configuration dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get(self, path, default=None):
        """Get configuration value by dot-separated path."""
        keys = path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, path, value):
        """Set configuration value by dot-separated path."""
        keys = path.split('.')
        config = self.config

        # Navigate to parent
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set final value
        config[keys[-1]] = value

    # Convenience properties for common values
    @property
    def wifi_ssid(self):
        return self.get("wifi.ssid", "")

    @property
    def wifi_password(self):
        return self.get("wifi.password", "")

    @property
    def wifi_url(self):
        return self.get("wifi.url", "")

    @property
    def wifi_url_qr(self):
        return self.get("wifi.url_qr", "")

    @property
    def has_wifi_config(self):
        """Check if WiFi is configured."""
        return bool(self.wifi_ssid and self.wifi_password)

    @property
    def homeassistant_enabled(self):
        return self.get("homeassistant.enabled", False)

    @property
    def homeassistant_config(self):
        """Get HomeAssistant configuration dict."""
        return self.get("homeassistant", {})

    @property
    def auto_connect(self):
        return self.get("badge.auto_connect", False)

    @property
    def debug(self):
        return self.get("badge.debug", False)

# Global configuration instance
_config_instance = None

def get_config():
    """Get or create the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance

# Convenience functions
def get_wifi_config():
    """Get WiFi configuration as tuple (ssid, password, url, url_qr)."""
    config = get_config()
    return (config.wifi_ssid, config.wifi_password, config.wifi_url, config.wifi_url_qr)

def has_wifi_config():
    """Check if WiFi is properly configured."""
    return get_config().has_wifi_config