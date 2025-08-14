import subprocess

def scan_wifi():
    options = []
    result = subprocess.run(["nmcli", "--fields", "SSID", "device", "wifi", "list"],
                                    stdout=subprocess.PIPE,
                                    text=True, check=True)
    scanoutput = result.stdout.strip()
    for line in scanoutput.split('\n'):
        print(line)
        if line[:5]  == "ESSID":
            ssid = line.split('ESSID:')[1].replace('"','')
            if ssid != '':
                options.append(ssid)
    return options

print(scan_wifi())