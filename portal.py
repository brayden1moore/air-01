from flask import Flask,request, render_template
import subprocess

app = Flask(__name__,
            static_folder='assets',
            template_folder='templates')

wifi_device = "wlan0"

subprocess.run(['sudo', 'nmcli','device', 'wifi', 'hotspot', 'ssid', 'Scud Radio', 'password', 'scudhouse'])

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
    return render_template('index.html', wifi_networks=wifi_networks)


@app.route('/submit',methods=['POST'])
def submit():
    if request.method == 'POST':
        print(*list(request.form.keys()), sep = ", ")
        ssid = request.form['ssid']
        password = request.form['password']

        result = subprocess.run(['nmcli', 'dev','wifi' ,'connect' ,ssid ,'password' ,password],stdout=subprocess.PIPE,text=True, check=True)
        if result.stderr:
            return "Error: failed to connect to wifi network: <i>%s</i>"
        elif result.stdout:
            return "Success: <i>%s</i>"
        return "Error: failed to connect."


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8888)