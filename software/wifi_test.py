import gc
import uasyncio as asyncio

async def test_wifi(wlan):
    """Run WiFi test using an existing WLAN interface."""
    print("\nStarting WiFi test")
    print("-----------------")
    
    print(f"Initial free memory: {gc.mem_free()}")
    
    try:
        was_active = wlan.active()
        if not was_active:
            print("\nActivating interface...")
            wlan.active(True)
            await asyncio.sleep_ms(1000)
        
        print(f"\nWLAN state:")
        print(f"Active: {wlan.active()}")
        print(f"Status: {wlan.status()}")
        print(f"Free memory: {gc.mem_free()}")
        
        print("\nAttempting scan...")
        try:
            nets = wlan.scan()
            print(f"Scan successful! Found {len(nets)} networks")
            print(f"Free memory after scan: {gc.mem_free()}")
            
            if nets:
                print("\nTop 3 networks by signal strength:")
                # Sort networks by RSSI (signal strength)
                nets.sort(key=lambda x: x[3], reverse=True)
                for i, net in enumerate(nets[:3]):
                    ssid = net[0]
                    if isinstance(ssid, bytes):
                        try:
                            ssid = ssid.decode('utf-8')
                        except:
                            ssid = str(ssid)
                    print(f"{i+1}. SSID: {ssid}")
                    print(f"   Signal: {net[3]}dB")
                    print(f"   Channel: {net[2]}")
                    auth = net[4]
                    sec_type = {
                        0: "Open",
                        1: "WEP",
                        2: "WPA-PSK",
                        3: "WPA2-PSK",
                        4: "WPA/WPA2-PSK"
                    }.get(auth, "Unknown")
                    print(f"   Security: {sec_type}")
                    print("")
        except Exception as e:
            print(f"\nScan failed!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
        
        if not was_active:
            print("\nRestoring interface state...")
            wlan.active(False)
        
    except Exception as e:
        print(f"WiFi test error: {type(e).__name__} - {str(e)}")
    finally:
        # Collect garbage to free any memory we used
        gc.collect()
    
    print(f"Final free memory: {gc.mem_free()}")