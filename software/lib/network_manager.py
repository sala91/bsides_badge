"""Network Manager for BSides Badge.

This module handles all WiFi functionality with proper error handling,
reconnection logic and power management.
"""

from micropython import const
import network
import time
import gc

# WiFi Constants
WIFI_CONNECT_TIMEOUT = const(10000)  # ms
WIFI_SCAN_TIMEOUT = const(10000)     # ms
MAX_CONNECT_RETRIES = const(3)
RECONNECT_WAIT_BASE = const(500)     # ms between retries, doubles each retry
WIFI_PM_ENABLE = True                # Enable power management

# Status/Error codes
WIFI_OK = const(0)
WIFI_ERR_CONFIG = const(1)
WIFI_ERR_NOT_FOUND = const(2) 
WIFI_ERR_AUTH_FAIL = const(3)
WIFI_ERR_CONNECT_FAIL = const(4)
WIFI_ERR_SCAN_FAIL = const(5)

# Singleton instance
_instance = None

class NetworkManager:
    """Manages WiFi connectivity with proper error handling and power management."""
    
    def __init__(self):
        self._wlan = None
        self._active = False
        self._last_error = WIFI_OK
        self._connect_retries = 0
        
    def init(self):
        """Initialize the WiFi interface."""
        if self._wlan is not None:
            return True
            
        # Force garbage collection before creating the interface
        gc.collect()
            
        try:
            self._wlan = network.WLAN(network.STA_IF)
            
            # Reduce buffer sizes if possible to save memory
            try:
                # Try to set smaller rx/tx buffers
                self._wlan.config(rxbuf=512)
                self._wlan.config(txbuf=512)
            except:
                pass
                
            if WIFI_PM_ENABLE:
                # Enable power save mode when supported
                try:
                    self._wlan.config(pm=network.WLAN.PM_POWERSAVE)
                except:
                    pass  # PM not supported
                    
            # Immediately deactivate until needed to free resources
            try:
                self._wlan.active(False)
            except:
                pass
                
            return True
        except Exception as e:
            self._last_error = WIFI_ERR_CONFIG
            print("WiFi init failed:", e)
            self._wlan = None
            gc.collect()  # Try to reclaim memory
            return False

    def active(self, active=None):
        """Get/set interface active state."""
        if active is None:
            return self._active if self._wlan else False
            
        if not self._wlan:
            if not self.init():
                return False
                
        try:
            self._wlan.active(active)
            self._active = active
            if not active:
                self._connect_retries = 0
            return True
        except Exception as e:
            print("WiFi active failed:", e)
            self._active = False
            return False

    def scan(self, timeout=WIFI_SCAN_TIMEOUT):
        """Scan for networks with timeout.
        
        Returns:
            List of tuples (ssid, bssid, channel, rssi, authmode, hidden) or None on error
        """
        if not self._ensure_active():
            return None
            
        # Force GC before scan to maximize available memory
        gc.collect()
            
        try:
            start = time.ticks_ms()
            result = None
            
            # Configure scan parameters to minimize memory usage
            try:
                # Try to set minimal scan config
                self._wlan.config(scan_hidden=False)  # Don't scan hidden networks
                self._wlan.config(scan_max=5)  # Limit number of results
            except:
                pass
                
            # Some implementations are async, retry until timeout
            while time.ticks_diff(time.ticks_ms(), start) < timeout:
                try:
                    result = self._wlan.scan()
                    if result is not None:
                        break
                except MemoryError:
                    # On memory error, force GC and retry once more
                    gc.collect()
                    time.sleep_ms(100)
                    try:
                        result = self._wlan.scan()
                        if result is not None:
                            break
                    except:
                        pass
                except:
                    pass
                time.sleep_ms(100)
                
            if result is None:
                self._last_error = WIFI_ERR_SCAN_FAIL
                print("WiFi scan timeout")
                return None
                
            # Force cleanup after scan
            gc.collect()
            return result
            
        except Exception as e:
            self._last_error = WIFI_ERR_SCAN_FAIL
            print("WiFi scan failed:", e)
            gc.collect()  # Try to reclaim memory
            return None

    def connect(self, ssid, password, timeout=WIFI_CONNECT_TIMEOUT):
        """Connect to a WiFi network with timeout and retry logic.
        
        Returns:
            True if connected successfully, False otherwise
        """
        if not self._ensure_active():
            return False
            
        # Reset connection state
        self._connect_retries = 0
        self._last_error = WIFI_OK
        
        while self._connect_retries < MAX_CONNECT_RETRIES:
            try:
                self._wlan.connect(ssid, password)
                
                # Wait for connection with timeout
                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < timeout:
                    status = self._wlan.status()
                    if status == network.STAT_GOT_IP:
                        print("WiFi connected")
                        return True
                    elif status == network.STAT_CONNECTING:
                        time.sleep_ms(100)
                    elif status == network.STAT_WRONG_PASSWORD:
                        self._last_error = WIFI_ERR_AUTH_FAIL
                        print("WiFi wrong password")
                        return False
                    elif status == network.STAT_NO_AP_FOUND:
                        self._last_error = WIFI_ERR_NOT_FOUND
                        break  # Retry
                    elif status == network.STAT_CONNECT_FAIL:
                        self._last_error = WIFI_ERR_CONNECT_FAIL
                        break  # Retry
                    else:
                        time.sleep_ms(100)
                
                # Handle retry
                self._connect_retries += 1
                if self._connect_retries < MAX_CONNECT_RETRIES:
                    wait_time = RECONNECT_WAIT_BASE * (2 ** self._connect_retries)
                    print(f"WiFi connect retry {self._connect_retries} in {wait_time}ms")
                    time.sleep_ms(wait_time)
                    gc.collect()  # Help with memory pressure
                
            except Exception as e:
                self._last_error = WIFI_ERR_CONNECT_FAIL
                print("WiFi connect error:", e)
                return False
                
        print("WiFi connect: max retries exceeded")
        return False

    def disconnect(self):
        """Disconnect from current network."""
        if self._wlan and self._wlan.active():
            try:
                self._wlan.disconnect()
                return True
            except Exception as e:
                print("WiFi disconnect failed:", e)
        return False

    def isconnected(self):
        """Check if currently connected."""
        return bool(self._wlan and self._wlan.isconnected())

    def status(self):
        """Get current status and error state.
        
        Returns:
            Tuple of (is_connected, last_error)
        """
        return (self.isconnected(), self._last_error)

    def ifconfig(self, config=None):
        """Get/set interface configuration (IP, subnet, gateway, DNS)."""
        if not self._wlan:
            return None
        if config is None:
            return self._wlan.ifconfig()
        try:
            self._wlan.ifconfig(config)
            return True
        except Exception as e:
            print("WiFi ifconfig failed:", e)
            return False

    def _ensure_active(self):
        """Ensure interface is initialized and active."""
        if not self._wlan and not self.init():
            return False
        if not self._active and not self.active(True):
            return False
        return True

def get_network_manager():
    """Get or create the NetworkManager singleton instance."""
    global _instance
    if _instance is None:
        _instance = NetworkManager()
    return _instance