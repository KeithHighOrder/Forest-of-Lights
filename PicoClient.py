import network
import urequests as requests
import time
import machine
import neopixel
import random
import ntptime

# Configuration
SSID = 'Attack On Eriegrove'
PASSWORD = 'Cowpuncher'
SERVER_IP = '192.168.0.48'
PICO_ID = 'pico1'

NUM_PIXELS = 20
pixels = neopixel.NeoPixel(machine.Pin(28), NUM_PIXELS)
button = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)

START_HOUR, END_HOUR = 17, 22  # Flicker timing in UTC
UTC_OFFSET = -4
NTP_SYNC_INTERVAL = 21600  # 6 hours
TARGET_LOOP_DURATION = 0.15  # 10 milliseconds for faster flicker updates
LED_OFF_CHANCE = 0.5  # Increase chance for more frequent flicker

def connect_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    print("Connecting to Wi-Fi", end="...")
    max_retries, retries = 100, 0
    while not wlan.isconnected() and retries < max_retries:
        print(".", end="")
        time.sleep(5)
        retries += 1
    if wlan.isconnected():
        print("\nConnected to Wi-Fi with IP:", wlan.ifconfig()[0])
    else:
        print("\nFailed to connect to Wi-Fi.")
    return wlan.isconnected()

def flicker():
    """Quick flicker effect with a higher chance of dim LEDs."""
    for i in range(NUM_PIXELS):
        if random.random() < LED_OFF_CHANCE:
            pixels[i] = (0, 5, 0)  # Dim flicker color
        else:
            pixels[i] = (5, 0, 15)  # Default spooky color (dim purple)

    pixels.write()  # Write all changes at once for faster flicker

def try_sync_ntp():
    try:
        ntptime.settime()
        print("Time synchronized successfully.")
        return time.time()
    except Exception as e:
        print("NTP sync failed:", e)
        return None

def post_button_state(state):
    try:
        response = requests.post(f"http://{SERVER_IP}:5005/update/{PICO_ID}", json={'button_state': state})
        response.close()
        print("Button state sent.")
    except Exception as e:
        print("Button state post failed:", e)

def get_led_color():
    try:
        response = requests.get(f"http://{SERVER_IP}:5005/led_state/{PICO_ID}")
        color = tuple(response.json().get('color', (0, 0, 0)))
        response.close()
        return color
    except Exception as e:
        print("Failed to retrieve LED command:", e)
        return None

# Initial Wi-Fi connection and NTP synchronization
if connect_wifi(SSID, PASSWORD):
    ntp_last_sync_time = try_sync_ntp()

last_button_state = button.value()
current_color = (0, 0, 0)

while True:
    loop_start_time = time.ticks_ms()
    
    # Reconnect Wi-Fi if disconnected
    if not network.WLAN(network.STA_IF).isconnected():
        print("Reconnecting Wi-Fi...")
        connect_wifi(SSID, PASSWORD)

    # Synchronize NTP time every NTP_SYNC_INTERVAL seconds
    if time.time() - ntp_last_sync_time > NTP_SYNC_INTERVAL:
        ntp_last_sync_time = try_sync_ntp() or ntp_last_sync_time

    # Get the current hour with UTC offset
    current_hour = (time.localtime()[3] + UTC_OFFSET) % 24
    button_state = not button.value()

    # Send button state update only if it has changed
    if button_state != last_button_state:
        post_button_state(button_state)
        last_button_state = button_state  # Update last known button state

    # Retrieve and set the LED color from the server
    color = get_led_color()
    if color and color != current_color:
        pixels.fill(color)
        pixels.write()
        current_color = color

    # Run the flicker effect if within the specified time window
    if color == (0, 0, 0) and START_HOUR <= current_hour < END_HOUR:
        flicker()  # Run the flicker continuously without delay

    # Control loop timing
    loop_end_time = time.ticks_ms()
    idle_time = max(0, TARGET_LOOP_DURATION - time.ticks_diff(loop_end_time, loop_start_time) / 1000)
    time.sleep(idle_time)

