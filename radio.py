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


def get_streams():
    url = 'https://internetradioprotocol.org/info'
    streams = requests.get(url).json()

    inactive_streams = []
    for name, value in streams.items():
        if value['status'] == "Offline":
            inactive_streams.append(name)

    for inactive_stream in inactive_streams:
        del streams[inactive_stream]

    return streams

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


def safe_display(image):
    global current_image
    if screen_on & (image != current_image):
        disp.display(image)
    current_image = image.copy()
    

def display_scud():
    img = Image.open('assets/dancers.png').resize((240, 240)) 
    font = ImageFont.truetype("assets/Silkscreen-Regular.ttf", 10)

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
    background = Image.new('RGB', (25, 25), color=(255, 255, 255))
    icon = Image.open('assets/pause.png').resize((25, 25))
    image.paste(background, (22, 35))
    image.paste(icon, (22, 35))
    safe_display(image)


def play(name):
    global mpv_process, current_image

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
    background = Image.new('RGB', (25, 25), color=(255, 255, 255))
    icon = Image.open('assets/play.png').resize((25, 25))
    image.paste(background, (22, 35))
    image.paste(icon, (22, 35))
    safe_display(image)


def display_everything(name):
    global streams, play_status

    image = Image.new('RGB', (240, 240), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)

    logo_url = streams[name]['logo']
    logo = Image.open(BytesIO(requests.get(logo_url).content)).resize((120, 120))
    border = Image.new('RGB', (122, 122), color=(255,255,255))
    image.paste(border, (24, 35))
    image.paste(logo, (25, 36))

    '''
    icon_path = f'assets/{play_status}.png'
    icon = Image.open(icon_path).resize((25, 25))
    image.paste(icon, (22,35))

    icon_path = f'assets/flower.png'
    icon = Image.open(icon_path).resize((30, 110))
    image.paste(icon, (19,75))
    '''

    font = ImageFont.truetype("assets/Silkscreen-Regular.ttf", 10)
    
    prev_stream = '< ' + stream_list[stream_list.index(name)-1][:10]
    try:
        next_stream = stream_list[stream_list.index(name)+1][:10] + ' >'
    except:
        next_stream = stream_list[0][:10] + ' >'

    draw.text((32, 10), '[play/pause]', font=font, fill=(255,255,255))
    draw.text((160, 10), '[random]', font=font, fill=(255,255,255))
    draw.text((10, 224), prev_stream, font=font, fill=(255,255,255))
    draw.text((230-len(next_stream)*6, 224), next_stream, font=font, fill=(255,255,255))

    # stream info
    background = Image.new('RGB', (240, 25), color=(0, 0, 0))
    image.paste(background, (24, 195))

    title = f"{name}"
    parts = [
        streams[name]['nowPlaying'],
        streams[name]['nowPlayingArtist'],
        streams[name]['nowPlayingSubtitle'],
        streams[name]['nowPlayingAdditionalInfo'],
    ]
    subtitle = " - ".join(p for p in parts if p)
    font = ImageFont.truetype("assets/Silkscreen-Regular.ttf", 20)
    draw.text((24, 155), title, font=font, fill=(255,255,255))
    font = ImageFont.truetype("assets/Silkscreen-Regular.ttf", 12)
    draw.text((24, 175), subtitle, font=font, fill=(255,255,255))

    show_logo_url = streams[name]['showLogo']
    if show_logo_url:
        try:
            show_logo = Image.open(BytesIO(requests.get(show_logo_url).content)).resize((140, 140))
            border = Image.new('RGB', (142, 142), color=(0,0,0))
            image.paste(border, (75, 35))
            image.paste(show_logo, (76, 36))
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
        blank = Image.new('RGB', (240, 240), color=(255, 255, 255))
        disp.display(blank)

    else:
        try:
            streams = get_streams()
            display_everything(stream)
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
