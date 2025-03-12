import st7789
from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button
from subprocess import Popen
import requests
from datetime import date
import time
import signal
from io import BytesIO

streams = {
    'X': {
        'name': 'KQED',
        'stream': 'https://streams.kqed.org/kqedradio?onsite=true',
        'info': 'https://media-api.kqed.org/radio-schedules/',
        'logo': 'kqed.png'
    },
    'Y': {
        'name': 'HydeFM',
        'stream': 'https://media.evenings.co/s/DReMy100B',
        'info': 'https://api.evenings.co/v1/streams/hydefm/public',
        'logo': 'hydefm.png'
    },
    'A': {
        'name': 'NTS 1',
        'stream': 'https://stream-relay-geo.ntslive.net/stream?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts1.png'
    },
    'B': {
        'name': 'NTS 2',
        'stream': 'https://stream-relay-geo.ntslive.net/stream2?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts2.png'
    },
}

# Setup Display
disp = st7789.ST7789(
    height=240,
    width=240,
    rotation=90,
    port=0,
    cs=1,
    dc=9,
    backlight=13,
    spi_speed_hz=80_000_000
)

disp.begin()

mpv_process = None

def display_info(logo_path, show_name):
    image = Image.new('RGB', (240, 240), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    logo_path = f'logos/{logo_path}'

    try:
        logo = Image.open(logo_path).resize((150, 150))
        image.paste(logo, (70, 20))
    except Exception as e:
        print(f"Failed to load logo: {e}")

    font = ImageFont.load_default()
    draw.text((10, 200), show_name, font=font, fill=(255, 255, 255))
    disp.display(image.rotate(-90))

def toggle_stream(button):
    global mpv_process

    stream_info = streams[button]
    stream_url = stream_info['stream']
    logo_path = stream_info['logo']
    name = stream_info['name']
    show_names = []

    if button == 'Y':
        info = requests.get(stream_info['info']).json()
        show_names.append(info.get('name', name))

    elif button in ['A', 'B']:
        info = requests.get(stream_info['info']).json()
        result_idx = 0 if button == 'A' else 1
        show_names.append(info['results'][result_idx]['now']['broadcast_title'])

    elif button == 'X':
        today = date.today().isoformat()
        epoch_time = int(time.time())
        info_url = stream_info['info'] + today
        info = requests.get(info_url).json()
        programs = info['data']['attributes']['schedule']
        for program in programs:
            if int(program['startTime']) < epoch_time:
                show_name = program['programTitle']
        show_names.append(program['programTitle'])

    display_info(logo_path, show_names[0])

    if mpv_process:
        mpv_process.send_signal(signal.SIGTERM)
        mpv_process = None
    else:
        mpv_process = Popen([
            "mpv",
            "--ao=alsa",
            "--audio-device=alsa/hw:1,0",
            "--volume=40",
            stream_url
        ])


button_x = Button(16)
button_y = Button(24)
button_a = Button(5)
button_b = Button(6)

button_x.when_pressed = lambda: toggle_stream('X')
button_y.when_pressed = lambda: toggle_stream('Y')
button_a.when_pressed = lambda: toggle_stream('A')
button_b.when_pressed = lambda: toggle_stream('B')

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    if mpv_process:
        mpv_process.terminate()

    WIDTH = disp.width
    HEIGHT = disp.height
    img = Image.new("RGB", (WIDTH, HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    disp.display(img)
