from PIL import Image, ImageDraw, ImageFont, ImageSequence
from subprocess import Popen, run
import subprocess
import requests
from datetime import date, datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import signal
from io import BytesIO
import threading
import random
import platform
import math
import os
import driver as LCD_2inch
import spidev as SPI

# 2 inch
RST = 27
DC = 25
BL = 23
bus = 0 
device = 0 
MAX_BL = 100
disp = LCD_2inch.LCD_2inch()
disp.Init()
disp.clear()
disp.bl_DutyCycle(MAX_BL)

mpv_process = None
stream = None
screen_on = True
current_image = None
saved_image_while_paused = None
play_status = 'pause'
last_input_time = time.time()
first_display = True
current_volume = 50 
volume_step = 5  
button_press_time = 0
rotated = False

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
FONT_SIZE = 6

BORDER_COLOR = (0,0,0)
TEXT_COLOR = (0,0,0)
TEXT_COLOR_2 = (100,100,100)
BACKGROUND_COLOR = (255,255,0)
BORDER_SIZE = 2

LOGO_SIZE = 140
LOGO_Y = 20
LOGO_X = round(SCREEN_WIDTH/2) - round(LOGO_SIZE/2)

SMALL_LOGO_SIZE = 60
SMALL_LOGO_Y = LOGO_Y + round(LOGO_SIZE/2) - round(SMALL_LOGO_SIZE/2)
PREV_LOGO_X = LOGO_X - round(SMALL_LOGO_SIZE) + 15 - BORDER_SIZE
NEXT_LOGO_X = LOGO_X + LOGO_SIZE - 15

TITLE_Y = LOGO_SIZE + LOGO_Y + 10
SUBTITLE_Y = TITLE_Y + 25
LOCATION_Y = SUBTITLE_Y + 15

STATUS_SIZE = 25
STATUS_LOCATION = (LOGO_X+round(LOGO_SIZE/2)-round(STATUS_SIZE/2), LOGO_Y+round(LOGO_SIZE/2)-round(STATUS_SIZE/2))

SMALL_FONT = ImageFont.truetype("assets/andalemono.ttf", 10)
MEDIUM_FONT = ImageFont.truetype("assets/andalemono.ttf", 12)
LARGE_FONT = ImageFont.truetype("assets/Silkscreen-Regular.ttf",20)
PAUSE_IMAGE = (Image.open('assets/pause.png').convert('RGBA').resize((LOGO_SIZE+BORDER_SIZE*2, LOGO_SIZE+BORDER_SIZE*2)))

def backlight_on():
    if disp:
        if current_image:
            safe_display(current_image)
        else:
            display_scud()
        disp.bl_DutyCycle(MAX_BL)
    #GPIO.output(BACKLIGHT_PIN, GPIO.HIGH)

def backlight_off():
    if disp:
        #display_scud()
        disp.bl_DutyCycle(0)
    #GPIO.output(BACKLIGHT_PIN, GPIO.LOW)

mpv_process = Popen([
    "mpv",
    "--idle=yes",
    "--no-video",
    "--ao=alsa",
    "--audio-device=alsa/hw:1,0",
    f"--volume={current_volume}",
    "--input-ipc-server=/tmp/mpvsocket"
])

import st7789
from gpiozero import Button
import socket
import json

def send_mpv_command(cmd):
    with socket.socket(socket.AF_UNIX) as s:
        s.connect("/tmp/mpvsocket")
        s.sendall((json.dumps(cmd) + '\n').encode())

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

# hat
'''
disp = st7789.ST7789(
    rotation=180,     # Needed to display the right way up on Pirate Audio
    port=0,          # SPI port
    cs=1,            # SPI port Chip-select channel
    dc=9,            # BCM pin used for data/command
    backlight=13,  # 13 for Pirate-Audio; 18 for back BG slot, 19 for front BG slot.
)
disp.begin()
'''


def x(string, font):
    text_width, _ = font.getsize(string)
    return max((SCREEN_WIDTH - text_width) // 2, 5)


def safe_display(image):
    global current_image
    if screen_on & (image != current_image):
        #disp.display(image)
        disp.ShowImage(image) # for 2 inch
    current_image = image.copy()
    

def display_scud():
    image = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT))
    rotations = 0
    while rotations <2:
        for i in [1,2,3,4,5,6,7]:
             
            bg = Image.open(f'assets/gif/{i}.png') 
            image.paste(bg, (0, 0))
            safe_display(image)  

            if i==1 and rotations==0:
                time.sleep(1)

        rotations += 1

    bg = Image.open(f'assets/gif/1.png') 
    image.paste(bg, (0, 0))
    safe_display(image)  
            

    '''
    bg = Image.open(f'assets/scudgif/background.png') 
    image.paste(bg, (0, 0))
    draw = ImageDraw.Draw(image)
    safe_display(image)

    img = Image.open(f'assets/scudgif/dancergifgif.gif')

    for frame in ImageSequence.Iterator(img):
        image.paste(img.resize((180,180)), (140, 0))
        draw = ImageDraw.Draw(image)
        safe_display(image)
    '''

display_scud()

def s(number):
    if number == 1:
        return ''
    else:
        return 's'
    

def write_to_tmp_os_path(name):
    file_path = os.path.join("/tmp", "scud_last_played.txt")
    
    with open(file_path, 'w') as file:
        file.write(name)


def read_last_played():
    file_path = os.path.join("/tmp", "scud_last_played.txt")

    try:
        with open(file_path, 'r') as file:
            last_played = file.read()
        
        return last_played
    except:
        return None

def pause(show_icon=False):
    global play_status, saved_image_while_paused, current_image
    #send_mpv_command({"command": ["stop"]})
    send_mpv_command({"command": ["set_property", "volume", 0]})

    if show_icon and current_image:
        saved_image_while_paused = current_image.copy()
        img = current_image.convert('RGBA')
        img.paste(PAUSE_IMAGE, (LOGO_X, LOGO_Y), PAUSE_IMAGE)
        safe_display(img.convert('RGB'))

    play_status = 'pause'


def play(name, toggled=False):
    global play_status, stream
    play_status = 'play'
    stream = name

    if toggled:
        safe_display(saved_image_while_paused)
        send_mpv_command({"command": ["set_property", "volume", current_volume]})
    else:
        stream_url = streams[name]['streamLink']
        send_mpv_command({"command": ["loadfile", stream_url, "replace"]})
        send_mpv_command({"command": ["set_property", "volume", current_volume]})

    write_to_tmp_os_path(name)


def display_everything(name, update=False):
    global streams, play_status, first_display

    first_display = False

    prev_stream = stream_list[stream_list.index(name)-1]
    try:
        next_stream = stream_list[stream_list.index(name)+1]
    except:
        next_stream = stream_list[0]

    image = Image.new('RGB', (SCREEN_WIDTH, SCREEN_HEIGHT), color=BACKGROUND_COLOR)
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

    '''
    show_logo_url = streams[name]['showLogo']
    if show_logo_url:
        try:
            show_logo = Image.open(BytesIO(requests.get(show_logo_url).content)).resize((LOGO_SIZE, LOGO_SIZE))
            border = Image.new('RGB', (LOGO_SIZE+BORDER_SIZE*2, LOGO_SIZE+BORDER_SIZE*2), color=BORDER_COLOR)
            image.paste(border, (LOGO_X, LOGO_Y))
            image.paste(show_logo, (LOGO_X+BORDER_SIZE, LOGO_Y+BORDER_SIZE))
        except:
            pass
    '''

    safe_display(image) # display 


def toggle_stream(name):
    global play_status
    if name:
        if play_status == 'play':
            pause(show_icon=True)
        else:
            play(name, toggled=True)

    
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

def show_volume_overlay(volume):
    global current_image

    if current_image:
        img = current_image.copy()
        draw = ImageDraw.Draw(img)
        
        bar_width = 320
        bar_height = 5
        bar_x = 0
        bar_y = 0 
        
        draw.rectangle([bar_x-2, bar_y-2, bar_x+bar_width+2, bar_y+bar_height+2], fill=BORDER_COLOR)
        draw.rectangle([bar_x, bar_y, bar_x+bar_width, bar_y+bar_height], fill=TEXT_COLOR)
        
        volume_width = int((volume / 100) * bar_width)
        draw.rectangle([bar_x, bar_y, bar_x+volume_width, bar_y+bar_height], fill=BACKGROUND_COLOR)
        
        safe_display(img)

def on_button_pressed():
    global button_press_time, rotated
    button_press_time = time.time()
    rotated = False

def on_button_released():
    global button_press_time, rotated
    
    if (time.time() - button_press_time < 0.2) and (time.time() - button_press_time > 0.05) and not rotated:
        if not wake_screen():
            toggle_stream(stream)


def handle_rotation(direction):
    global rotated, current_volume, button_press_time
    rotated = True

    if click_button.is_pressed:

        if direction == 1: 
            current_volume = min(100, current_volume + volume_step)
        else: 
            current_volume = max(0, current_volume - volume_step)

        send_mpv_command({"command": ["set_property", "volume", current_volume]})
        show_volume_overlay(current_volume)

    else:
        if (time.time() - button_press_time > 1):
            seek_stream(direction)

def shutdown():
    run(['sudo', 'shutdown', 'now'])

def periodic_update():
    global screen_on, last_input_time, streams, stream_list
    if screen_on and (time.time() - last_input_time > 60):
        screen_on = False
        backlight_off()
    else:
        try:
            info = requests.get('https://internetradioprotocol.org/info').json()
            for name, v in info.items():
                if name in streams:
                    streams[name].update(v)
            stream_list = list(streams.keys())

            if play_status != 'pause':
                display_everything(stream, update=True)
                
        except Exception as e:
            print(e)
            pass
    threading.Timer(60, periodic_update).start()


def wake_screen():
    global screen_on, last_input_time, current_image
    last_input_time = time.time()
    if not screen_on:
        screen_on = True
        backlight_on()
        if current_image:
            #disp.display(current_image)
            disp.ShowImage(current_image) # for 2 inch
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
    backlight_off()
    run([
        'sudo',
        'systemctl',
        'stop',
        'radio'
    ])

from gpiozero import RotaryEncoder, Button

click_button = Button(26)
click_button.when_pressed = on_button_pressed
click_button.when_released = on_button_released

CLK_PIN = 5 
DT_PIN = 6   
rotor = RotaryEncoder(CLK_PIN, DT_PIN)
rotor.when_rotated_counter_clockwise = wrapped_action(lambda: handle_rotation(-1))
rotor.when_rotated_clockwise = wrapped_action(lambda: handle_rotation(1))

#button_x = Button(16, hold_time=5)
#button_y = Button(24, hold_time=5)
#button_a = Button(5, hold_time=5)
#button_b = Button(6, hold_time=5)

#button_b.when_pressed = wrapped_action(lambda: toggle_stream(stream))
#button_a.when_pressed = wrapped_action(play_random)
#button_y.when_pressed = wrapped_action(lambda: seek_stream(-1))
#button_x.when_pressed = wrapped_action(lambda: seek_stream(1))
#button_b.when_held = restart

last_played = read_last_played()
if last_played:
    play(last_played)
else:
    play_random()

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
    #disp.display(img)
    disp.ShowImage(img) # for 2 inch
