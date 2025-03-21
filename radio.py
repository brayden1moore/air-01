import st7789
from PIL import Image, ImageDraw, ImageFont, ImageSequence
from gpiozero import Button
from subprocess import Popen, run
import requests
from datetime import date, datetime, timezone
import time
import signal
from io import BytesIO
import threading
import random

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
    'Dublab': {
        'name': 'Dublab',
        'stream': 'https://dublab.out.airtime.pro/dublab_a',
        'info': 'https://www.dublab.com/.netlify/functions/schedule?tz=America%2FLos_Angeles',
        'logo': 'dublab.jpeg'
    },
    #'Lower Grand Radio': {
    #    'name': 'Lower Grand Radio',
    #    'stream': 'https://lowergrandradio.out.airtime.pro:8000/lowergrandradio_a',
    #    'info': 'https://lowergrandradio.airtime.pro/api/live-info-v2',
    #},
    'Fault Radio': {
        'name': 'Fault Radio',
        'stream': 'https://player.twitch.tv/?autoplay=1&channel=Faultradio&parent=www.faultradio.com',
        'info': '',
        'logo': 'fault.png'
    }
}

stream_list = sorted(list(streams.keys()))

disp = st7789.ST7789(
    height=240,
    width=240,
    rotation=180,
    port=0,
    cs=1,
    dc=9,
    backlight=13,
    spi_speed_hz=80_000_000
)

disp.begin()

mpv_process = None
stream = None

def display_scud():
    gif = Image.open('assets/scudhouse.gif').resize((240, 240)) 
    frame = ImageSequence.Iterator(gif)[0].convert('RGB')
    font = ImageFont.load_default()

    image = Image.new('RGB', (240, 240))
    image.paste(frame, (0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((35, 10), 'play/pause', font=font, fill=(0, 0, 0))
    draw.text((165, 10), 'random', font=font, fill=(0, 0, 0))
    draw.text((37, 220), 'previous', font=font, fill=(0, 0, 0))
    draw.text((170, 220), 'next', font=font, fill=(0, 0, 0))
    disp.display(image)

display_scud()


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
    logo_urls = []

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

    elif name == 'Dublab':
        now = datetime.now(timezone.utc)
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        show_name = 'Dublab'
        description = 'No description.'
        for program in info:
            if datetime.fromisoformat(program['startTime']) < now:
                show_name = program['eventTitleMeta']['artist'] if program['eventTitleMeta']['artist'] else "Dublab"                
                description = program['eventTitleMeta']['eventName']
                logo_url = program['attachments']
        show_names.append(show_name)
        descriptions.append(description) 
        logo_urls.append(logo_url)

    show_names = [i.replace('\u2019', "'").replace('\u2013', "-").replace('&#039;',"'").replace('\u201c','"').replace('\u201d','"') for i in show_names]
    descriptions = [i.replace('\u2019', "'").replace('\u2013', "-").replace('&#039;',"'").replace('\u201c','"').replace('\u201d','"') for i in descriptions]

    image = Image.new('RGB', (240, 240), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)

    if len(logo_urls)>0:
        response = requests.get(logo_urls[0])
        logo = Image.open(BytesIO(response.content)).resize((150, 150))
    else:
        logo_path = f'logos/{logo_path}'
        logo = Image.open(logo_path).resize((150, 150))

    border = Image.new('RGB', (152, 152), color=(255, 255, 255))
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
    
    disp.display(image)


def toggle_stream(name):
    global mpv_process, stream

    if name != None:

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
                    "--no-video",
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
                "--no-video",
                stream_url
            ])
            stream = name
            display_info(name, 'play')

def play_random():
    available_streams = [i for i in stream_list if i != stream]
    chosen = random.choice(available_streams)
    toggle_stream(chosen)

def seek_stream(direction):
    if stream == None:
        play_random()
    
    else:
        idx = stream_list.index(stream)
        try:
            toggle_stream(stream_list[idx + direction])
        except:
            if direction == 1:
                toggle_stream(stream_list[0])
            else:
                toggle_stream(stream_list[-1])


def shutdown():
    run(['sudo', 'shutdown', 'now'])


def periodic_update():
    global mpv_process
    if mpv_process and mpv_process.poll() is None:
        display_info(stream, 'play')

    threading.Timer(5, periodic_update).start()

button_x = Button(16, hold_time=5)
button_y = Button(24, hold_time=5)
button_a = Button(5, hold_time=5)
button_b = Button(6, hold_time=5)

button_b.when_pressed = lambda: toggle_stream(stream)
button_a.when_pressed = lambda: play_random()
button_y.when_pressed = lambda: seek_stream(-1)
button_x.when_pressed = lambda: seek_stream(1)

periodic_update()

try:
    while True:
        time.sleep(0.5)
except KeyboardInterrupt:
    if mpv_process:
        mpv_process.terminate()

    WIDTH = disp.width
    HEIGHT = disp.height
    img = Image.new("RGB", (WIDTH, HEIGHT), color="black")
    draw = ImageDraw.Draw(img)
    disp.display(img)
