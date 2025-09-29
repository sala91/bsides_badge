"""Network Manager for BSides Badge.

Simple, working WiFi singleton - no fancy features, just connect and go.
Based on the original working implementation.
"""

import network
import gc

# Singleton instance
_instance = None

class NetworkManager:
    """Simple WiFi manager - singleton pattern for shared WLAN interface."""

    def __init__(self):
        self._wlan = None
        self._initialized = False

    def init(self):
        """Initialize the WiFi interface."""
        if self._initialized:
            return True

        gc.collect()

        try:
            self._wlan = network.WLAN(network.STA_IF)
            self._initialized = True
            return True

        except Exception as e:
            print("WiFi init failed:", e)
            self._wlan = None
            gc.collect()
            return False

    def get_interface(self):
        """Get the WLAN interface, initializing if needed."""
        if not self._initialized:
            self.init()
        return self._wlan

def get_network_manager():
    """Get or create the NetworkManager singleton instance."""
    global _instance
    if _instance is None:
        _instance = NetworkManager()
    return _instance