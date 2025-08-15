from flask import Flask,request, render_template, session, redirect, url_for
import subprocess
import socket
import sys
import time


app = Flask(__name__,
            static_folder='assets',
            template_folder='templates')

wifi_device = "wlan0"

def internet(host="8.8.8.8", port=53, timeout=3):
    """
    Host: 8.8.8.8 (google-public-dns-a.google.com)
    OpenPort: 53/tcp
    Service: domain (DNS/TCP)
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error as ex:
        print(ex)
        return False

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

@app.route('/')
def index():
    wifi_networks = scan_wifi()
    return render_template('index.html', wifi_networks=wifi_networks, message="")

@app.route('/submit', methods=['POST'])
def submit():
    if request.method == 'POST':
        print(*list(request.form.keys()), sep=", ")
        ssid = request.form['ssid']
        password = request.form['password']
        
        try:
            result = subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, check=True)
            
            time.sleep(6)
            if internet():
                print("Starting radio")
                subprocess.run(['sudo','systemctl','restart','radio'])
                return redirect(url_for('success'))
            else:
                return redirect(url_for('index', wifi_networks=scan_wifi(), message="That didn't work."))
                
        except subprocess.CalledProcessError as e:
            return redirect(url_for('index', wifi_networks=scan_wifi(), message="That didn't work."))

    return "Error: Invalid request method."

@app.route('/success', methods=['GET'])
def success():
    return render_template('success.html')

if __name__ == '__main__':
    connected = internet()

    if not connected:
        subprocess.run(['sudo', 'nmcli','device', 'wifi', 'hotspot', 'ssid', 'Scud Radio', 'password', 'scudhouse'])
        app.run(debug=True, host='0.0.0.0', port=8888)
    else:
        print("Internet connection already available. No configuration needed.")
        print("Starting radio")
        subprocess.run(['sudo','systemctl','restart','radio'])
        sys.exit(0)