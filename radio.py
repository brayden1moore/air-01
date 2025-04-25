from PIL import Image, ImageDraw, ImageFont, ImageSequence
from subprocess import Popen, run
import requests
from datetime import date, datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import signal
from io import BytesIO
import threading
import random
import platform
import RPi.GPIO as GPIO # type: ignore

BACKLIGHT_PIN = 13
GPIO.setmode(GPIO.BCM)
GPIO.setup(BACKLIGHT_PIN, GPIO.OUT)
FONT_SIZE = 6

LOGO_SIZE = 150
LOGO_Y = 20
LOGO_X = round(240/2) - round(LOGO_SIZE/2)

SMALL_LOGO_SIZE = 60
SMALL_LOGO_Y = LOGO_Y + round(LOGO_SIZE/2) - round(SMALL_LOGO_SIZE/2)
PREV_LOGO_X = LOGO_X - round(SMALL_LOGO_SIZE * 0.66)
NEXT_LOGO_X = 240 - SMALL_LOGO_SIZE - round(SMALL_LOGO_SIZE * (0.33/2))

TITLE_Y = LOGO_SIZE + LOGO_Y + 10
SUBTITLE_Y = TITLE_Y + 25
LOCATION_Y = SUBTITLE_Y + 15

STATUS_SIZE = 25
STATUS_LOCATION = (LOGO_X+round(LOGO_SIZE/2)-round(STATUS_SIZE/2), LOGO_Y+round(LOGO_SIZE/2)-round(STATUS_SIZE/2))

BORDER_COLOR = (125,125,125)
TEXT_COLOR = (255,255,255)
TEXT_COLOR_2 = (225,225,225)
BACKGROUND_COLOR = (0,0,0)
BORDER_SIZE = 2

SMALL_FONT = ImageFont.truetype("assets/Silkscreen-Regular.ttf", 10)
MEDIUM_FONT = ImageFont.truetype("assets/Silkscreen-Regular.ttf", 12)
LARGE_FONT = ImageFont.truetype("assets/Silkscreen-Regular.ttf",20)
PAUSE_IMAGE = (Image.open('assets/pause.png').convert('RGBA').resize((LOGO_SIZE+BORDER_SIZE*2, LOGO_SIZE+BORDER_SIZE*2)))

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


def fetch_logo(name, url):
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return name, BytesIO(resp.content)

def get_streams():
    global streams

    info = requests.get('https://internetradioprotocol.org/info').json()
    active = {n: v for n, v in info.items() if v['status']=="Online"}
    
    with ThreadPoolExecutor(max_workers=8) as exe:
        futures = [
            exe.submit(fetch_logo, name, v['logo'])
            for name, v in active.items()
        ]
        for f in as_completed(futures):
            name, buf = f.result()
            active[name]['logoBytes'] = buf

            img = Image.open(buf).convert('RGB')
            active[name]['logo_full']  = img.resize((LOGO_SIZE,  LOGO_SIZE))
            active[name]['logo_small'] = img.resize((SMALL_LOGO_SIZE, SMALL_LOGO_SIZE))

    return active

streams = get_streams()
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
play_status = 'pause'
last_input_time = time.time()

def x(string, font):
    text_width, _ = font.getsize(string)
    return max((240 - text_width) // 2, 0)


def safe_display(image):
    global current_image
    if screen_on & (image != current_image):
        disp.display(image)
    current_image = image.copy()
    

def display_scud():
    img = Image.open('assets/dancers.png').resize((240, 240)) 
    image = Image.new('RGB', (240, 240))
    image.paste(img, (0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((32, 10), '[play/pause]', font=SMALL_FONT, fill=(0, 0, 0))
    draw.text((160, 10), '[random]', font=SMALL_FONT, fill=(0, 0, 0))
    prev_stream = '< ' + stream_list[-1][:10]
    next_stream = stream_list[0][:10] + ' >'
    draw.text((10, 224), prev_stream, font=SMALL_FONT, fill=(0, 0, 0))
    draw.text((230-len(next_stream)*6, 224), next_stream, font=SMALL_FONT, fill=(0, 0, 0))
    safe_display(image)

display_scud()


def s(number):
    if number == 1:
        return ''
    else:
        return 's'
    

def pause():
    global mpv_process, current_image, play_status

    if mpv_process:
        mpv_process.send_signal(signal.SIGTERM)
        mpv_process = None

    img = current_image.convert('RGBA')
    img.paste(PAUSE_IMAGE, (LOGO_X, LOGO_Y), PAUSE_IMAGE)

    safe_display(img.convert('RGB'))
    play_status = 'pause'


def play(name):
    global mpv_process, current_image, play_status

    stream_url = streams[name]['streamLink']

    mpv_process = Popen([
        "mpv",
        "--ao=alsa",
        "--audio-device=alsa/hw:1,0",
        "--volume=90",
        "--no-video",
        stream_url
    ])

    image = current_image.copy()
    #icon = Image.open('assets/play.png').resize((25, 25))
    #image.paste(icon, STATUS_LOCATION)
    safe_display(image)
    play_status = 'play'


def display_everything(name, update=False):
    global streams, play_status

    prev_stream = stream_list[stream_list.index(name)-1]
    try:
        next_stream = stream_list[stream_list.index(name)+1]
    except:
        next_stream = stream_list[0]

    image = Image.new('RGB', (240, 240), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(image)

    logo = streams[name]['logo_full']
    prev = streams[prev_stream]['logo_small']
    next = streams[next_stream]['logo_small']

    border = Image.new('RGB', (SMALL_LOGO_SIZE+BORDER_SIZE*2, SMALL_LOGO_SIZE+BORDER_SIZE*2), color=BORDER_COLOR)
    image.paste(border, (PREV_LOGO_X, SMALL_LOGO_Y))
    image.paste(border, (NEXT_LOGO_X, SMALL_LOGO_Y))
    image.paste(prev, (PREV_LOGO_X+BORDER_SIZE, SMALL_LOGO_Y+BORDER_SIZE))
    image.paste(next, (NEXT_LOGO_X+BORDER_SIZE, SMALL_LOGO_Y+BORDER_SIZE))

    border = Image.new('RGB', (LOGO_SIZE+BORDER_SIZE*2, LOGO_SIZE+BORDER_SIZE*2), color=BORDER_COLOR)
    image.paste(border, (LOGO_X, LOGO_Y))
    image.paste(logo, (LOGO_X+BORDER_SIZE, LOGO_Y+BORDER_SIZE))

    title = f"{name}"
    parts = [
        streams[name]['nowPlaying'],
        streams[name]['nowPlayingArtist'],
        streams[name]['nowPlayingSubtitle'],
        streams[name]['nowPlayingAdditionalInfo'],
    ]
    subtitle = " - ".join(p for p in parts if p)
    location = streams[name]['location']

    draw.text((x(title, LARGE_FONT), TITLE_Y), title, font=LARGE_FONT, fill=TEXT_COLOR)
    draw.text((x(subtitle, MEDIUM_FONT), SUBTITLE_Y), subtitle, font=MEDIUM_FONT, fill=TEXT_COLOR_2)
    draw.text((x(location, MEDIUM_FONT), LOCATION_Y), location, font=MEDIUM_FONT, fill=TEXT_COLOR_2)

    show_logo_url = streams[name]['showLogo']
    if show_logo_url:
        try:
            show_logo = Image.open(BytesIO(requests.get(show_logo_url).content)).resize((LOGO_SIZE, LOGO_SIZE))
            border = Image.new('RGB', (LOGO_SIZE+BORDER_SIZE*2, LOGO_SIZE+BORDER_SIZE*2), color=BORDER_COLOR)
            image.paste(border, (LOGO_X, LOGO_Y))
            image.paste(show_logo, (LOGO_X+BORDER_SIZE, LOGO_Y+BORDER_SIZE))
        except:
            pass

    safe_display(image) # display 


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
    global stream, play_status
    pause()
    available_streams = [i for i in stream_list if i != stream]
    chosen = random.choice(available_streams)
    display_everything(chosen)
    play(chosen)
    stream = chosen
    play_status = 'play'


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
    global screen_on, last_input_time, streams
    if screen_on and (time.time() - last_input_time > 60):
        screen_on = False
        backlight_off()
    else:
        try:
            streams = get_streams()
            stream_list = list(streams.keys())
            display_everything(stream, update=True)
        except:
            pass
    threading.Timer(60, periodic_update).start()


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
