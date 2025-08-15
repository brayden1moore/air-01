from flask import Flask,request
import subprocess

app = Flask(__name__)

wifi_device = "wlan0"

subprocess.run(['sudo', 'nmcli','device', 'wifi', 'hotspot', 'ssid', 'scud.local:8888', 'password', 'scudhouse'])

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
    dropdowndisplay = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <link rel="icon" type="image/png" href="/favicon/favicon-96x96.png" sizes="96x96" />
            <link rel="icon" type="image/svg+xml" href="/favicon/favicon.svg" />
            <link rel="shortcut icon" href="/favicon/favicon.ico" />
            <link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png" />
            <link rel="manifest" href="/favicon/site.webmanifest"/>,
            <meta name="viewport" content="width=device-width, initial-scale=1"><meta charset="UTF-8"><title>Internet Radio Protocol</title></head><body style="font-family:Andale Mono; padding:10vw; padding-top:10px;"><div style="display:flex; justify-content:center"><img id="main-logo" src="assets/scudradiocenter.gif" alt="Loading" width="auto"></div>
            <title>Set Up Your Scud Radio</title>
        </head>
        <body>
            <h1>Wifi Control</h1>
            <form action="/submit" method="post">
                <label for="ssid">Choose a WiFi network:</label>
                <select name="ssid" id="ssid">
        """
    for ssid in scan_wifi():
        dropdowndisplay += f"""
                <option value="{ssid}">{ssid}</option>
            """
    dropdowndisplay += """
                </select>
                <p/>
                <label for="password">Password: <input type="password" name="password"/></label>
                <p/>
                <input type="submit" value="Connect">
            </form>
        <style>
            body {
                background-color: yellow;
            }
        </style>
        </body>
        </html>
        """
    return dropdowndisplay


@app.route('/submit',methods=['POST'])
def submit():
    if request.method == 'POST':
        print(*list(request.form.keys()), sep = ", ")
        ssid = request.form['ssid']
        password = request.form['password']

        result = subprocess.run(['nmcli', 'dev','wifi' ,'connect' ,ssid ,'password' ,password],stdout=subprocess.PIPE,text=True, check=True)
        if result.stderr:
            return "Error: failed to connect to wifi network: <i>%s</i>" % result.stderr.decode()
        elif result.stdout:
            return "Success: <i>%s</i>"
        return "Error: failed to connect."


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8888)