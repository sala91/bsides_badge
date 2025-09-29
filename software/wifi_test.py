import network
import gc
import time

def test_wifi():
    print("\nStarting WiFi test")
    print("-----------------")
    
    # Memory before anything
    print(f"Initial free memory: {gc.mem_free()}")
    
    # Create interface
    print("\nCreating WLAN interface...")
    wlan = network.WLAN(network.STA_IF)
    print(f"Free memory after creating WLAN: {gc.mem_free()}")
    
    # Check initial state
    print(f"\nInitial WLAN state:")
    print(f"Active: {wlan.active()}")
    print(f"Status: {wlan.status()}")
    
    # Activate interface
    print("\nActivating interface...")
    wlan.active(True)
    time.sleep(1)  # Give it time to initialize
    print(f"Active after setting: {wlan.active()}")
    print(f"Status after setting: {wlan.status()}")
    print(f"Free memory: {gc.mem_free()}")
    
    # Try scan
    print("\nAttempting scan...")
    try:
        nets = wlan.scan()
        print(f"Scan successful! Found {len(nets)} networks")
        print(f"Free memory after scan: {gc.mem_free()}")
        
        # Try to print first network if any
        if nets:
            net = nets[0]
            print(f"\nFirst network:")
            print(f"SSID: {net[0]}")
            print(f"RSSI: {net[3]}")
    except Exception as e:
        print(f"\nScan failed!")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"Free memory: {gc.mem_free()}")
    
    # Cleanup
    print("\nCleaning up...")
    wlan.active(False)
    print(f"Final free memory: {gc.mem_free()}")

if __name__ == "__main__":
    test_wifi()