from PIL import Image, ImageDraw, ImageFont, ImageSequence
from subprocess import Popen, run
import requests
from datetime import date, datetime, timezone, timedelta
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
        'logo': 'nts1.png',
        'location': 'London'
    },
    'NTS 2': {
        'name': 'NTS 2',
        'stream': 'https://stream-relay-geo.ntslive.net/stream2?client=NTSWebApp&device=800913353.1735584982',
        'info': 'https://www.nts.live/api/v2/live',
        'logo': 'nts2.png',
        'location': 'London'
    },
    'Dublab': {
        'name': 'Dublab',
        'stream': 'https://dublab.out.airtime.pro/dublab_a',
        'info': 'https://www.dublab.com/.netlify/functions/schedule?tz=America%2FLos_Angeles',
        'logo': 'dublab.jpeg',
        'location': 'Los Angeles'
    },
    'WNYU': {
        'name': 'WNYU',
        'stream': 'http://cinema.acs.its.nyu.edu:8000/wnyu128.mp3',
        'info': 'https://wnyu.org/v1/schedule/current_and_next',
        'logo': 'wnyu.jpeg',
        'location': 'New York'
    },
    'The Lot Radio': {
        'name': 'The Lot Radio',
        'stream': ' https://lax-prod-catalyst-0.lp-playback.studio/hls/video+85c28sa2o8wppm58/0_1/index.m3u8?tkn=jUpPJwZzBI7EVJxGzkp0C8',
        'info': 'thelotradio.com_j1ordgiru5n55sa5u312tjgm9k@group.calendar.google.com',
        'location': 'Brooklyn',
        'logo': 'thelot.jpeg'
    },
    'Voices': {
        'name': 'Voices',
        'stream': 'https://voicesradio.out.airtime.pro/voicesradio_a',
        'info': 'https://voicesradio.airtime.pro/api/live-info-v2?timezone=America/Los_Angeles',
        'logo': 'voices.jpeg',
        'location': 'London'
    },
    'Bloop Radio': {
        'name': 'Bloop Radio',
        'stream': 'https://radio.canstream.co.uk:8058/live.mp3',
        'info': 'https://blooplondon.com/wp-admin/admin-ajax.php?action=radio_station_current_show',
        'logo': 'bloop.png',
        'location': 'London'
    },
    'Radio Quantica': {
        'name': 'Radio Quantica',
        'stream': 'https://stream.radioquantica.com:8443/stream',
        'info': 'https://api.radioquantica.com/api/live-info',
        'logo': 'quantica.jpeg',
        'location': 'Lisbon'
    },
    'HydeFM': {
        'name': 'HydeFM',
        'stream': 'https://media.evenings.co/s/DReMy100B',
        'info': 'https://api.evenings.co/v1/streams/hydefm/public',
        'logo': 'hydefm.png',
        'location': 'San Francisco'
    },
    'Do!!You!!!': {
        'name': 'Do!!You!!!',
        'stream': 'https://doyouworld.out.airtime.pro/doyouworld_a',
        'info': 'https://doyouworld.airtime.pro/api/live-info-v2',
        'logo': 'doyou.png',
        'location': 'Los Angeles'
    },
    'SutroFM': {
        'name': 'SutroFM',
        'stream': 'https://media.evenings.co/s/7Lo66BLQe',
        'info': 'https://api.evenings.co/v1/streams/sutrofm/public',
        'logo': 'sutrofm.jpeg',
        'location': 'San Francisco'
    },
    'KQED': {
        'name': 'KQED',
        'stream': 'https://streams.kqed.org/kqedradio?onsite=true',
        'info': 'https://media-api.kqed.org/radio-schedules/',
        'logo': 'kqed.png',
        'location': 'San Francisco'
    },
    'Lower Grand Radio': {
        'name': 'Lower Grand Radio',
        'stream': 'https://lowergrandradio.out.airtime.pro:8000/lowergrandradio_a',
        'info': 'https://lowergrandradio.airtime.pro/api/live-info-v2',
        'logo': 'lgr.png',
        'location': 'Oakland'
    },
    'We Are Various': {
        'name': 'We Are Various',
        'stream': 'https://azuracast.wearevarious.com/listen/we_are_various/live.mp3',
        'info': 'https://azuracast.wearevarious.com/api/nowplaying/we_are_various',
        'logo': 'various.jpeg',
        'location': 'Antwerp'
    },
    'Kiosk Radio': {
        'name': 'Kiosk Radio',
        'stream': 'https://kioskradiobxl.out.airtime.pro/kioskradiobxl_b',
        'info': 'https://kioskradiobxl.airtime.pro/api/live-info-v2',
        'logo': 'kiosk.webp',
        'location': 'Brussels'
    },
    'Internet Public Radio': {
        'name': 'Internet Public Radio',
        'stream': 'https://c11.radioboss.fm:18270/stream?_ic2=1744737620752',
        'info': 'https://c11.radioboss.fm/w/nowplayinginfo?u=270&1744737649518',
        'logo': 'internet.png',
        'location': 'Guadalajara'
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

    background = Image.new('RGB', (240, 20), color=(0, 0, 0))
    image.paste(background, (24, 195))
    draw.text((24, 195), name, font=font, fill=(255, 255, 255))
    draw.text((24, 205), "Loading info...", font=font, fill=(255, 255, 0))

    safe_display(image)
    display_info(name)


def display_info(name):
    global current_image

    stream_info = streams[name]

    show_names = []
    descriptions = []
    locations = []

    # evening
    if name in ['HydeFM','SutroFM']:
        info = requests.get(stream_info['info']).json()
        status = info['online']
        show_title = info.get('name', name)
        num_listeners = info['listeners']
        listeners = f"{num_listeners} listener{s(num_listeners)}."
        locations.append(stream_info['location'])

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
        location = show_info['embeds']['details']['location_long']
        if not description:
            genres = []
            for g in show_info['embeds']['details']['genres']:
                genres.append(g['value']) 
                descriptions.append(', '.join(genres))
        else:
            descriptions.append(description)
        if not location:
            locations.append(stream_info['location'])
        else: 
            locations.append(location)

        show_names.append(show_info['broadcast_title'])

    elif name == 'KQED':
        today = date.today().isoformat()
        epoch_time = int(time.time())
        info_url = stream_info['info'] + today
        info = requests.get(info_url).json()
        programs = info['data']['attributes']['schedule']
        show_name = name
        description = 'No description.'        
        for program in programs:
            if int(program['startTime']) < epoch_time:
                show_name = program['programTitle']
                description = program['programDescription']
        
        show_names.append(show_name)
        locations.append(stream_info['location'])
        descriptions.append(description) 

    elif name == 'Dublab':
        now = datetime.now(timezone.utc)
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        show_name = name
        description = 'No description.'
        for program in info:
            if datetime.fromisoformat(program['startTime']) < now:
                show_name = program['eventTitleMeta']['artist'] if program['eventTitleMeta']['artist'] else "Dublab"                
                description = program['eventTitleMeta']['eventName']
                
        show_names.append(show_name)
        descriptions.append(description)
        locations.append(stream_info['location']) 
    
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
        locations.append(stream_info['location']) 

    elif name == 'The Lot Radio':
        
        api_key = 'AIzaSyD7jIVZog7IC--y1RBCiLuUmxEDeBH9wDA'
        calendar_id = stream_info['info']
        time_minus_1hr = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(microsecond=0).isoformat()

        url = f'https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events'
        params = {
            'key': api_key,
            'maxResults': 3,
            'singleEvents': True,
            'orderBy': 'startTime',
            'timeMin': time_minus_1hr
        }

        response = requests.get(url, params=params)
        data = response.json()

        for event in data.get('items', []):
            end_time_str = event['end']['dateTime']
            end_time = datetime.fromisoformat(end_time_str)

            start_time_str = event['start']['dateTime']
            start_time = datetime.fromisoformat(start_time_str)

            now_utc = datetime.now(timezone.utc)

            if end_time > now_utc > start_time:
                show_names.append(event['summary'])
        
        locations.append(stream_info['location'])
        descriptions.append('No description.')
    
    elif name == 'Radio Quantica':
        info_url = stream_info['info']
        info = requests.get(info_url).json()
        show_name = info['currentShow'][0]['name']
        show_names.append(show_name)
        locations.append(stream_info['location']) 
        descriptions.append('No description.')

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
        locations.append(stream_info['location']) 

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
        show_names.append(response['current-show']['showName'])
        locations.append(stream_info['location']) 
        descriptions.append('No description.')
    
    elif name == 'Internet Public Radio':
        url = stream_info['info']
        info = requests.get(url).json()
        show_names.append(info['nowplaying'])
        locations.append(stream_info['location']) 
        descriptions.append('No description.')

    elif name == 'We Are Various':
        url = stream_info['info']
        info = requests.get(url).json()
        show_names.append(info['now_playing']['song']['title'])
        locations.append(stream_info['location']) 
        descriptions.append('No description.')


    font = ImageFont.load_default()
    image = current_image.copy()
    draw = ImageDraw.Draw(image)

    background = Image.new('RGB', (240, 20), color=(0, 0, 0))
    image.paste(background, (24, 195))

    try:
        show_names = [i.replace('&amp;','&').replace('\u2019', "'").replace('\u2013', "-").replace('&#039;',"'").replace('\u201c','"').replace('\u201d','"').replace('\n',' ') for i in show_names]
        descriptions = [i.replace('&amp;','&').replace('\u2019', "'").replace('\u2013', "-").replace('&#039;',"'").replace('\u201c','"').replace('\u201d','"').replace('\n',' ') for i in descriptions]
        
        title = f'{name} ({locations[0]})'
        
        draw.text((24, 195), title, font=font, fill=(255, 255, 255))
        draw.text((24, 205), show_names[0][:40], font=font, fill=(255, 255, 0))
    except:
        draw.text((24, 195), title, font=font, fill=(255, 255, 255))
        draw.text((24, 205), "No description.", font=font, fill=(255, 255, 0))

    safe_display(image)


def toggle_stream(name):
    global mpv_process
    if name:
        if mpv_process:
            pause()
        else:
            play(name)
    else:
        pass

    
def play_random():
    global stream
    pause()
    available_streams = [i for i in stream_list if i != stream]
    chosen = random.choice(available_streams)
    display_everything(chosen)
    play(chosen)
    stream = chosen


def seek_stream(direction):
    global stream 
    pause()

    if (stream == None) & (direction==1):
        stream = stream_list[0]       

    elif (stream == None) & (direction==-1):
        stream = stream_list[-1]

    else:
        idx = stream_list.index(stream)
        if (direction == 1) and (idx==len(stream_list)-1):
            stream = stream_list[0]
        elif (direction == -1) and (idx==0):
            stream = stream_list[-1]
        else:
            stream = stream_list[idx + direction]

    display_everything(stream)
    play(stream)


def shutdown():
    run(['sudo', 'shutdown', 'now'])


def periodic_update():
    global screen_on, last_input_time
    if screen_on and (time.time() - last_input_time > 60):
        screen_on = False
        backlight_off()
        blank = Image.new('RGB', (240, 240), color=(0, 0, 0))
        disp.display(blank)

    else:
        try:
            display_info(stream)
        except:
            pass
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


def restart():
    run([
        'sudo',
        'systemctl',
        'restart',
        'radio'
    ])


button_x = Button(16, hold_time=5)
button_y = Button(24, hold_time=5)
button_a = Button(5, hold_time=5)
button_b = Button(6, hold_time=5)

button_b.when_pressed = wrapped_action(lambda: toggle_stream(stream))
button_a.when_pressed = wrapped_action(play_random)
button_y.when_pressed = wrapped_action(lambda: seek_stream(-1))
button_x.when_pressed = wrapped_action(lambda: seek_stream(1))

button_b.when_held = restart

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
