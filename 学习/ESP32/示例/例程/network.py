def do_connect():
    import network
    print('connecting to network...')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print('connecting to network...')
        wlan.connect('YOUR_WIFI_SSID', 'YOUR_WIFI_PASSWORD')
        while not wlan.isconnected():
            pass
    print('network config:', wlan.ifconfig())
    
do_connect()