import st7789
from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button
from subprocess import Popen, run
import requests
from datetime import date
import time
import signal
from io import BytesIO
import threading

streams = {
    'KQED': {
        'name': 'KQED',
        'stream': 'https://streams.kqed.org/kqedradio?onsite=true',
        'info': 'https://media-api.kqed.org/radio-schedules/',
        'logo': 'kqed.png'
    },
    'HydeFM': {
        'name': 'HydeFM',
        'stream': 'https://media.evenings.co/s/DReMy100B',
        'info': 'https://api.evenings.co/v1/streams/hydefm/public',
        'logo': 'hydefm.png'
    },
    'NTS 2': {
        'name': 'NTS 2',
        'stream': 'https://stream-relay-geo.ntslive.net/stream2?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts2.png'
    },
    'NTS 1': {
        'name': 'NTS 1',
        'stream': 'https://stream-relay-geo.ntslive.net/stream?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts1.png'
    },
}

button_mappings = {
    'A':'NTS 2',
    'B':'NTS 1',
    'X':'KQED',
    'Y':'Hyde FM'
}

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
#image = Image.new('RGB', (240, 240), color=(0, 0, 0))
#draw = ImageDraw.Draw(image)

#for button, name in button_mappings.items():
#    logo_path = streams[name]['logo']
#    logo_path = f'logos/{logo_path}'
#    border = Image.new('RGB', (57, 57), color=(255, 255, 255))
#    logo = Image.open(logo_path).resize((55, 55))
#
#    if button=='A':
#        image.paste(border, (3, 3))
#        image.paste(logo, (5, 5))
#    elif button=='B':
#        image.paste(border, (240-57-3, 3))
#        image.paste(logo, (240-55-5, 5))

#disp.display(image.rotate(180))

mpv_process = None
stream = None

def s(number):
    if number == 1:
        return ''
    else:
        return 's'

def display_info(name, play_status):

    stream_info = streams[name]
    logo_path = stream_info['logo']
    show_names = []
    descriptions = []

    if name == 'HydeFM':
        info = requests.get(stream_info['info']).json()
        status = info['online']
        show_title = info.get('name', name)
        num_listeners = info['listeners']
        listeners = f"{num_listeners} listener{s(num_listeners)}."
        descriptions.append(listeners)

        if status == False:
            show_names.append('OFFLINE')
        else:
            show_names.append(show_title)

    elif 'NTS' in name:
        info = requests.get(stream_info['info']).json()
        result_idx = 0 if name == 'NTS 1' else 1
        show_info = info['results'][result_idx]['now']

        genres = []
        for g in show_info['embeds']['details']['genres']:
            genres.append(g['value']) 
        
        if len(genres)==0:
            descriptions.append(show_info['embeds']['details']['description'])
        else:
            descriptions.append(', '.join(genres))

        show_names.append(show_info['broadcast_title'])

    elif name == 'KQED':
        today = date.today().isoformat()
        epoch_time = int(time.time())
        info_url = stream_info['info'] + today
        info = requests.get(info_url).json()
        programs = info['data']['attributes']['schedule']
        show_name = 'KQED'
        description = 'No description.'
        for program in programs:
            if int(program['startTime']) < epoch_time:
                show_name = program['programTitle']
                description = program['programDescription']
        show_names.append(show_name)
        descriptions.append(description) 

    show_names = [i.replace('\u2019', "'").replace('&#039;',"'") for i in show_names]
    descriptions = [i.replace('\u2019', "'").replace('&#039;',"'") for i in descriptions]

    image = Image.new('RGB', (240, 240), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    logo_path = f'logos/{logo_path}'
    border = Image.new('RGB', (152, 152), color=(255, 255, 255))
    logo = Image.open(logo_path).resize((150, 150))
    image.paste(border, (69, 19))
    image.paste(logo, (70, 20))

    icon_path = f'assets/{play_status}.png'
    icon = Image.open(icon_path).resize((30, 30))
    image.paste(icon, (19,19))

    icon_path = f'assets/flower.png'
    icon = Image.open(icon_path).resize((30, 110))
    image.paste(icon, (19,65))

    font = ImageFont.load_default()
    draw.text((19, 195), show_names[0], font=font, fill=(255, 255, 255))
    draw.text((19, 205), descriptions[0], font=font, fill=(255, 255, 255))
    
    disp.display(image.rotate(180))

def toggle_stream(name):
    global mpv_process, stream

    stream_info = streams[name]
    stream_url = stream_info['stream']

    if mpv_process: # if stream is playing, stop it
        mpv_process.send_signal(signal.SIGTERM)
        mpv_process = None

        display_info(name, 'pause')

        if stream != name: # if the button pressed is a new stream, play it
            mpv_process = Popen([ 
                "mpv",
                "--ao=alsa",
                "--audio-device=alsa/hw:1,0",
                "--volume=50",
                stream_url
            ])
            stream = name
            display_info(name, 'play')

    else: # otherwise play the one pressed
        mpv_process = Popen([
            "mpv",
            "--ao=alsa",
            "--audio-device=alsa/hw:1,0",
            "--volume=50",
            stream_url
        ])
        stream = name
        display_info(name, 'play')
        
def shutdown():
    run(['sudo', 'shutdown', 'now'])

def periodic_update():
    if mpv_process:
        display_info(stream, 'play')
    threading.Timer(5, periodic_update).start()

button_x = Button(16, hold_time=5)
button_y = Button(24, hold_time=5)
button_a = Button(5, hold_time=5)
button_b = Button(6, hold_time=5)

button_b.when_pressed = lambda: toggle_stream('NTS 1')
button_a.when_pressed = lambda: toggle_stream('NTS 2')
button_y.when_pressed = lambda: toggle_stream('HydeFM')
button_x.when_pressed = lambda: toggle_stream('KQED')

periodic_update()

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
