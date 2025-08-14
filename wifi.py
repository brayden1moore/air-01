from subprocess import check_output

def scan_wifi():
    options = []
    scanoutput = check_output(["iwlist", "wlan0", "scan"])
    for line in scanoutput.split():
        line = line.decode("utf-8")
        if line[:5]  == "ESSID":
            ssid = line.split('"')[1]
            options.append(ssid)
    return options

print(scan_wifi())