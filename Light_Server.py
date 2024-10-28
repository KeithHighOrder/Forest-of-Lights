from flask import Flask, jsonify
import threading
import pygame
import logging
from threading import Lock
import os
import atexit

app = Flask(__name__)

# Initialize logging
logging.basicConfig(level=logging.INFO)

# State to track button presses and LED colors
pico_states = {
    'pico1': {'button_state': False, 'color': (0, 0, 0)},
    'pico2': {'button_state': False, 'color': (0, 0, 0)},
    'pico3': {'button_state': False, 'color': (0, 0, 0)},
    'pico4': {'button_state': False, 'color': (0, 0, 0)},
}

# Global variables for game state
timer_active = False
window_duration = 5  # Time window in seconds
required_buttons_pressed = 4  # Number of clients that need to press the button to succeed
state_lock = Lock()
audio_timer = None

# Audio setup
audio_file = "/home/pi/Rick.mp3"
pygame_initialized = False

def init_pygame():
    global pygame_initialized
    try:
        pygame.mixer.init()
        pygame_initialized = True
        logging.info("Pygame mixer initialized.")
    except pygame.error as e:
        logging.error(f"Failed to initialize pygame mixer: {e}")

# Initialize pygame if audio file exists
if os.path.exists(audio_file):
    init_pygame()
else:
    logging.error("Audio file not found. Please check the path.")

def reset_game():
    """Reset the game state for a new round."""
    global timer_active, audio_timer
    with state_lock:
        for pico_id in pico_states:
            pico_states[pico_id]['button_state'] = False
            pico_states[pico_id]['color'] = (0, 0, 0)
        timer_active = False
    if audio_timer:
        audio_timer.cancel()
    logging.info("Game reset. Waiting for button presses.")

def check_for_success():
    """Check if the required number of buttons were pressed within the window duration."""
    with state_lock:
        buttons_pressed = sum(pico['button_state'] for pico in pico_states.values())

    if buttons_pressed >= required_buttons_pressed:
        logging.info(f"Success! {buttons_pressed} buttons pressed within the time window.")
        set_green_all()
        play_audio()  # Audio will be played after success
    else:
        logging.info(f"Only {buttons_pressed} buttons pressed. Resetting game.")
        reset_game()

def set_green_all():
    """Turn all clients green for a short duration."""
    with state_lock:
        for pico_id in pico_states:
            pico_states[pico_id]['color'] = (0, 255, 0)
    threading.Timer(1, reset_game).start()

def play_audio():
    """Play the success audio file if pygame is initialized."""
    global audio_timer
    if not pygame_initialized or not os.path.exists(audio_file):
        logging.error("Audio file not found or pygame not initialized. Skipping audio.")
        reset_game()
        return

    try:
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        logging.info(f"Playing audio: {audio_file}")

        # Non-blocking check to reset after audio finishes
        def check_audio_finished():
            if pygame.mixer.music.get_busy():
                audio_timer = threading.Timer(0.5, check_audio_finished)
                audio_timer.start()
            else:
                reset_game()
        
        check_audio_finished()
    except pygame.error as e:
        logging.error(f"Error playing audio: {e}")
        reset_game()

@app.route('/update/<pico_id>', methods=['POST'])
def update_button_state(pico_id):
    global timer_active

    if pico_id in pico_states:
        with state_lock:
            if not pico_states[pico_id]['button_state']:
                pico_states[pico_id]['button_state'] = True
                pico_states[pico_id]['color'] = (255, 0, 0)
                logging.info(f"{pico_id} button pressed - LEDs turned red.")

                if not timer_active:
                    timer_active = True
                    threading.Timer(window_duration, check_for_success).start()

        return jsonify(success=True)
    else:
        return jsonify(success=False, error="Invalid Pico ID"), 400

@app.route('/led_state/<pico_id>', methods=['GET'])
def get_led_state(pico_id):
    if pico_id in pico_states:
        color = pico_states[pico_id]['color']
        return jsonify(color=color)
    else:
        return jsonify(success=False, error="Invalid Pico ID"), 400

@atexit.register
def cleanup():
    if pygame_initialized:
        pygame.mixer.quit()
        logging.info("Pygame mixer quit successfully.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005)
