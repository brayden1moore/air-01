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
    #'Lower Grand Radio': {
    #    'name': 'Lower Grand Radio',
    #    'stream': 'https://lowergrandradio.out.airtime.pro:8000/lowergrandradio_a',
    #    'info': 'https://lowergrandradio.airtime.pro/api/live-info-v2',
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

    elif name == 'Do!!You!!!':
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        try:
            show_name = info['shows']['current']['name']
            description = info['tracks']['current']['name'].replace(' - ','')
        except:
            show_name = 'Do!!You!!!Radio'
            description = 'Is offline.'
        show_names.append(show_name)
        descriptions.append(description) 

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
    try:
        draw.text((19, 195), show_names[0], font=font, fill=(255, 255, 255))
        draw.text((19, 205), descriptions[0], font=font, fill=(255, 255, 255))
    except:
        draw.text((19, 195), name, font=font, fill=(255, 255, 255))
        draw.text((19, 205), "No description.", font=font, fill=(255, 255, 255))
    
    draw.text((35, 10), 'play/pause', font=font, fill=(0, 0, 0))
    draw.text((165, 10), 'random', font=font, fill=(0, 0, 0))
    draw.text((37, 220), 'previous', font=font, fill=(0, 0, 0))
    draw.text((170, 220), 'next', font=font, fill=(0, 0, 0))
    safe_display(image)


def toggle_stream(name):
    global mpv_process, stream, last_stream_time
    last_stream_time = time.time()

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
                    "--volume=90",
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
                "--volume=90",
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
    
    if (stream == None) & (direction==1):
        toggle_stream(stream_list[0])
    
    elif (stream == None) & (direction==-1):
        toggle_stream(stream_list[-1])

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
