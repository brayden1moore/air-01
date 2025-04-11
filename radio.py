from PIL import Image, ImageDraw, ImageFont, ImageSequence
from subprocess import Popen, run
import requests
from datetime import date, datetime, timezone
import time
import signal
from io import BytesIO
import threading
import random
import platform
import RPi.GPIO as GPIO

BACKLIGHT_PIN = 13
GPIO.setmode(GPIO.BCM)
GPIO.setup(BACKLIGHT_PIN, GPIO.OUT)
FONT_SIZE = 6

def backlight_on():
    GPIO.output(BACKLIGHT_PIN, GPIO.HIGH)

def backlight_off():
    GPIO.output(BACKLIGHT_PIN, GPIO.LOW)

backlight_on()

if platform.system() == "Linux":
    import st7789
    from gpiozero import Button
else:
    class MockDisplay:
        def __init__(self, *args, **kwargs):
            self.width = 240
            self.height = 240

        def begin(self):
            pass

        def display(self, img):
            pass

    st7789 = type('st7789', (), {'ST7789': MockDisplay})

    class Button:
        def __init__(self, pin, hold_time=None):
            self.when_pressed = None

streams = {
    'NTS 1': {
        'name': 'NTS 1',
        'stream': 'https://stream-relay-geo.ntslive.net/stream?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts1.png'
    },
    'NTS 2': {
        'name': 'NTS 2',
        'stream': 'https://stream-relay-geo.ntslive.net/stream2?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts2.png'
    },
    'Dublab': {
        'name': 'Dublab',
        'stream': 'https://dublab.out.airtime.pro/dublab_a',
        'info': 'https://www.dublab.com/.netlify/functions/schedule?tz=America%2FLos_Angeles',
        'logo': 'dublab.jpeg'
    },
    'WNYU': {
        'name': 'WNYU',
        'stream': 'http://cinema.acs.its.nyu.edu:8000/wnyu128.mp3',
        'info': 'https://wnyu.org/v1/schedule/current_and_next',
        'logo': 'wnyu.jpeg'
    },
    'Voices': {
        'name': 'Voices',
        'stream': 'https://voicesradio.out.airtime.pro/voicesradio_a',
        'info': 'https://voicesradio.airtime.pro/api/live-info-v2?timezone=America/Los_Angeles',
        'logo': 'voices.jpeg'
    },
    'Bloop Radio': {
        'name': 'Bloop Radio',
        'stream': 'https://radio.canstream.co.uk:8058/live.mp3',
        'info': 'https://blooplondon.com/wp-admin/admin-ajax.php?action=radio_station_current_show',
        'logo': 'bloop.png'
    },
    'Radio Quantica': {
        'name': 'Radio Quantica',
        'stream': 'https://stream.radioquantica.com:8443/stream',
        'info': 'https://api.radioquantica.com/api/live-info',
        'logo': 'quantica.jpeg'
    },
    'HydeFM': {
        'name': 'HydeFM',
        'stream': 'https://media.evenings.co/s/DReMy100B',
        'info': 'https://api.evenings.co/v1/streams/hydefm/public',
        'logo': 'hydefm.png'
    },
    'Do!!You!!!': {
        'name': 'Do!!You!!!',
        'stream': 'https://doyouworld.out.airtime.pro/doyouworld_a',
        'info': 'https://doyouworld.airtime.pro/api/live-info-v2',
        'logo': 'doyou.png'
    },
    'SutroFM': {
        'name': 'SutroFM',
        'stream': 'https://media.evenings.co/s/7Lo66BLQe',
        'info': 'https://api.evenings.co/v1/streams/sutrofm/public',
        'logo': 'sutrofm.jpeg'
    },
    'KQED': {
        'name': 'KQED',
        'stream': 'https://streams.kqed.org/kqedradio?onsite=true',
        'info': 'https://media-api.kqed.org/radio-schedules/',
        'logo': 'kqed.png'
    },
    'Lower Grand Radio': {
        'name': 'Lower Grand Radio',
        'stream': 'https://lowergrandradio.out.airtime.pro:8000/lowergrandradio_a',
        'info': 'https://lowergrandradio.airtime.pro/api/live-info-v2',
        'logo': 'lgr.png'
    },
    'Kiosk Radio': {
        'name': 'Kiosk Radio',
        'stream': 'https://kioskradiobxl.out.airtime.pro/kioskradiobxl_b',
        'info': 'https://kioskradiobxl.airtime.pro/api/live-info-v2',
        'logo': 'kiosk.webp'
    }
        #'BlueMoonRadio': {
    #    'name': 'BlueMoonRadio',
    #    'stream': '',
    #    'info': '',
    #    'logo': 'bluemoon.png'
    #}
    #'Fault Radio': {
    #    'name': 'Fault Radio',
    #    'stream': 'https://player.twitch.tv/?autoplay=1&channel=Faultradio',
    #    'info': '',
    #    'logo': 'fault.png'
    #},
}

stream_list = list(streams.keys())

disp = st7789.ST7789(
    rotation=180,     # Needed to display the right way up on Pirate Audio
    port=0,          # SPI port
    cs=1,            # SPI port Chip-select channel
    dc=9,            # BCM pin used for data/command
    backlight=13,  # 13 for Pirate-Audio; 18 for back BG slot, 19 for front BG slot.
)

disp.begin()

mpv_process = None
stream = None
screen_on = True
current_image = None
last_input_time = time.time()


def safe_display(image):
    global current_image
    if screen_on:
        disp.display(image)
    current_image = image.copy()
    

def display_scud():
    img = Image.open('assets/dancers.png').resize((240, 240)) 
    font = ImageFont.load_default()

    image = Image.new('RGB', (240, 240))
    image.paste(img, (0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((32, 10), '[play/pause]', font=font, fill=(0, 0, 0))
    draw.text((160, 10), '[random]', font=font, fill=(0, 0, 0))
    prev_stream = '< ' + stream_list[-1]
    next_stream = stream_list[0] + ' >'
    draw.text((10, 224), prev_stream, font=font, fill=(0, 0, 0))
    draw.text((230-len(next_stream)*6, 224), next_stream, font=font, fill=(0, 0, 0))
    safe_display(image)

display_scud()


def s(number):
    if number == 1:
        return ''
    else:
        return 's'
    

def pause():
    global mpv_process, current_image

    if mpv_process:
        mpv_process.send_signal(signal.SIGTERM)
        mpv_process = None
    
    image = current_image.copy()
    background = Image.new('RGB', (25, 25), color=(0, 0, 0))
    icon = Image.open('assets/pause.png').resize((25, 25))
    image.paste(background, (22, 35))
    image.paste(icon, (22, 35))
    safe_display(image)


def play(name):
    global mpv_process, current_image

    stream_info = streams[name]
    stream_url = stream_info['stream']

    mpv_process = Popen([
        "mpv",
        "--ao=alsa",
        "--audio-device=alsa/hw:1,0",
        "--volume=90",
        "--no-video",
        stream_url
    ])

    image = current_image.copy()
    background = Image.new('RGB', (25, 25), color=(0, 0, 0))
    icon = Image.open('assets/play.png').resize((25, 25))
    image.paste(background, (22, 35))
    image.paste(icon, (22, 35))
    safe_display(image)


def display_everything(name, play_status='pause'):
    stream_info = streams[name]
    logo_path = stream_info['logo']

    image = Image.new('RGB', (240, 240), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)

    logo_path = f'logos/{logo_path}'
    logo = Image.open(logo_path).resize((140, 140))

    border = Image.new('RGB', (142, 142), color=(255, 255, 255))
    image.paste(border, (75, 35))
    image.paste(logo, (76, 36))

    icon_path = f'assets/{play_status}.png'
    icon = Image.open(icon_path).resize((25, 25))
    image.paste(icon, (22,35))

    icon_path = f'assets/flower.png'
    icon = Image.open(icon_path).resize((30, 110))
    image.paste(icon, (19,75))

    font = ImageFont.load_default()
    
    prev_stream = '< ' + stream_list[stream_list.index(name)-1]
    try:
        next_stream = stream_list[stream_list.index(name)+1] + ' >'
    except:
        next_stream = stream_list[0] + ' >'

    draw.text((32, 10), '[play/pause]', font=font, fill=(100, 100, 100))
    draw.text((160, 10), '[random]', font=font, fill=(100, 100, 100))
    draw.text((10, 224), prev_stream, font=font, fill=(100, 100, 100))
    draw.text((230-len(next_stream)*6, 224), next_stream, font=font, fill=(100, 100, 100))
    safe_display(image)

    display_info()


def display_info():
    global current_image

    name = stream 
    stream_info = streams[name]

    show_names = []
    descriptions = []

    # evening
    if name in ['HydeFM','SutroFM']:
        info = requests.get(stream_info['info']).json()
        status = info['online']
        show_title = info.get('name', name)
        num_listeners = info['listeners']
        listeners = f"{num_listeners} listener{s(num_listeners)}."

        if status == False:
            show_names.append(name)
            descriptions.append('Is offline.')
        else:
            show_names.append(show_title)
            descriptions.append(listeners)

    elif 'NTS' in name:
        info = requests.get(stream_info['info']).json()
        result_idx = 0 if name == 'NTS 1' else 1
        show_info = info['results'][result_idx]['now']

        description = show_info['embeds']['details']['description']
        print(show_info['embeds']['details']['description'])
        if not description:
            genres = []
            for g in show_info['embeds']['details']['genres']:
                genres.append(g['value']) 
                descriptions.append(', '.join(genres))
        else:
            descriptions.append(description)
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
    
    elif name == 'WNYU':
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        id = info[0]['id']
        description_url = f'https://wnyu.org/v1/schedule/{id}'
        info = requests.get(description_url).json()
        show_name = info['program']['name']
        description = ', '.join([i.title() for i in info['episode']['genre_list']])
        show_names.append(show_name)
        descriptions.append(description) 
    
    elif name == 'Radio Quantica':
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        description = info['currentShow'][0]['name']
        descriptions.append(description)
        show_names.append('Radio Quantica')

    # airtime
    elif name in ['Do!!You!!!','Voices','Lower Grand Radio','Kiosk Radio']:
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        try:
            show_name = info['shows']['current']['name']
            description = info['tracks']['current']['name'].replace(' - ','')
        except:
            show_name = name
            description = 'Is offline.'
        show_names.append(show_name)
        descriptions.append(description) 

    elif name == 'Bloop Radio':
        url = stream_info['info']
        payload = {
            'action': 'show-time-curd',
            'crud-action': 'read',
            'read-type': 'current'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Mozilla/5.0'
        }
        response = requests.post(url, data=payload, headers=headers).json()
        descriptions.append(response['current-show'])
        show_names.append(name)

    show_names = [i.replace('&amp;','&').replace('\u2019', "'").replace('\u2013', "-").replace('&#039;',"'").replace('\u201c','"').replace('\u201d','"') for i in show_names]
    descriptions = [i.replace('&amp;','&').replace('\u2019', "'").replace('\u2013', "-").replace('&#039;',"'").replace('\u201c','"').replace('\u201d','"') for i in descriptions]

    font = ImageFont.load_default()
    image = ImageDraw.Draw(current_image)
    draw = ImageDraw.Draw(image)

    image = current_image.copy()
    background = Image.new('RGB', (240, 20), color=(0, 0, 0))
    image.paste(background, (24, 195))

    try:
        draw.text((24, 195), show_names[0], font=font, fill=(255, 255, 255))
        draw.text((24, 205), descriptions[0], font=font, fill=(255, 255, 0))
    except:
        draw.text((24, 195), name, font=font, fill=(255, 255, 255))
        draw.text((24, 205), "No description.", font=font, fill=(255, 255, 0))

    safe_display(image)


def toggle_stream(name):
    global stream

    if name == stream:
        pause()
    else:
        play(name)

    
def play_random():
    available_streams = [i for i in stream_list if i != stream]
    chosen = random.choice(available_streams)
    display_everything(chosen)
    toggle_stream(chosen)


def seek_stream(direction):
    global stream 

    if (stream == None) & (direction==1):
        display_info(stream_list[0])
        stream = stream_list[0]
    
    elif (stream == None) & (direction==-1):
        display_info(stream_list[-1])
        stream = stream_list[-1]

    else:
        idx = stream_list.index(stream)
        try:
            display_info(stream_list[idx + direction])
            stream = stream_list[-1]
        except:
            if direction == 1:
                display_info(stream_list[0])
                stream = stream_list[0]
            else:
                display_info(stream_list[-1])
                stream = stream_list[-1]


def shutdown():
    run(['sudo', 'shutdown', 'now'])


def periodic_update():
    global screen_on, last_input_time
    if screen_on and (time.time() - last_input_time > 60):
        screen_on = False
        backlight_off()
        blank = Image.new('RGB', (240, 240), color=(0, 0, 0))
        disp.display(blank)

    threading.Timer(5, periodic_update).start()

def wake_screen():
    global screen_on, last_input_time, current_image
    last_input_time = time.time()
    if not screen_on:
        screen_on = True
        backlight_on()
        if current_image:
            disp.display(current_image)
        else:
            display_scud()
        return True
    return False


def wrapped_action(func):
    def inner():
        if not wake_screen():
            func()
    return inner


button_x = Button(16, hold_time=5)
button_y = Button(24, hold_time=5)
button_a = Button(5, hold_time=5)
button_b = Button(6, hold_time=5)

button_b.when_pressed = wrapped_action(lambda: toggle_stream(stream))
button_a.when_pressed = wrapped_action(play_random)
button_y.when_pressed = wrapped_action(lambda: seek_stream(-1))
button_x.when_pressed = wrapped_action(lambda: seek_stream(1))

periodic_update()

if platform.system() != 'Linux':
    from pynput import keyboard

    def on_press(key):
        try:
            if key.char == 'u':  # B
                toggle_stream(stream)
            elif key.char == 'i':  # A
                play_random()
            elif key.char == 'j':  # Y
                seek_stream(-1)
            elif key.char == 'k':  # X
                seek_stream(1)
        except AttributeError:
            pass

    listener = keyboard.Listener(on_press=on_press)
    listener.start()

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
