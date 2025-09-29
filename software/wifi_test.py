import gc
import time
from lib.network_manager import get_network_manager, WIFI_OK

def test_wifi():
    """Test WiFi functionality using NetworkManager."""
    print("\nStarting WiFi test")
    print("-----------------")
    
    # Memory before anything
    print(f"Initial free memory: {gc.mem_free()}")
    
    # Get network manager instance
    print("\nInitializing Network Manager...")
    nm = get_network_manager()
    
    if not nm.init():
        print("Failed to initialize network manager!")
        return
    
    print(f"Free memory after init: {gc.mem_free()}")
    
    # Check initial state
    print(f"\nInitial WiFi state:")
    print(f"Active: {nm.active()}")
    connected, last_error = nm.status()
    print(f"Connected: {connected}")
    print(f"Last error: {last_error}")
    
    # Activate interface 
    print("\nActivating interface...")
    if not nm.active(True):
        print("Failed to activate interface!")
        return
        
    print(f"Active after setting: {nm.active()}")
    print(f"Free memory: {gc.mem_free()}")
    
    # Try scan
    print("\nAttempting scan...")
    nets = nm.scan()
    if nets:
        print(f"Scan successful! Found {len(nets)} networks")
        print(f"Free memory after scan: {gc.mem_free()}")
        
        # Try to print first network if any
        if nets:
            net = nets[0]
            print(f"\nFirst network:")
            print(f"SSID: {net[0].decode() if isinstance(net[0], bytes) else net[0]}")
            print(f"RSSI: {net[3]}")
    else:
        print("\nScan failed!")
        print(f"Last error: {nm.status()[1]}")
        print(f"Free memory: {gc.mem_free()}")
    
    # Cleanup
    print("\nCleaning up...")
    nm.active(False)
    print(f"Final free memory: {gc.mem_free()}")

if __name__ == "__main__":
    test_wifi()