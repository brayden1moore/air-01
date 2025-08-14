import subprocess

def scan_wifi():
    options = []
    result = subprocess.run(["nmcli", "--fields", "SSID", "device", "wifi", "list"],
                                    stdout=subprocess.PIPE,
                                    text=True, check=True)
    scanoutput = result.stdout.strip()
    for line in scanoutput.split('\n')[1:]:
        ssid = line.strip()
        if ssid != '--':
            options.append(ssid)
    return options

options = scan_wifi()
print("Which wifi?")
for idx, i in enumerate(options):
    print(idx, ' -- ', i)
ssid = options[int(input())]
print("Password?")
password = input()
subprocess.run(['sudo','nmcli', 'dev','wifi' ,'connect' ,ssid ,'password' ,password])
