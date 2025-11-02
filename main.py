from flask import Flask, make_response, send_file, Response, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import cv2
import io
import piexif
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
import re
from gpiozero import AngularServo, OutputDevice, PWMOutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Define GPIO pins
PWMA = 12
PWMB = 13
AIN1 = 3
AIN2 = 2
STBY = 4
BIN1 = 20
BIN2 = 21
SERVO1_PIN = 26  # Camera servo 1 (horizontal/pan)
SERVO2_PIN = 6   # Camera servo 2 (vertical/tilt)

# Initialize GPIO Zero with PiGPIOFactory (for all devices to avoid jitter)
factory = PiGPIOFactory()

# Initialize motor control devices
pwmA = PWMOutputDevice(PWMA, pin_factory=factory, frequency=100)
pwmB = PWMOutputDevice(PWMB, pin_factory=factory, frequency=100)
ain1 = OutputDevice(AIN1, pin_factory=factory)
ain2 = OutputDevice(AIN2, pin_factory=factory)
bin1 = OutputDevice(BIN1, pin_factory=factory)
bin2 = OutputDevice(BIN2, pin_factory=factory)
stby = OutputDevice(STBY, pin_factory=factory)

# Initialize servos using GPIO Zero with PiGPIOFactory to avoid jitter
servo1 = AngularServo(SERVO1_PIN, min_angle=0, max_angle=180, min_pulse_width=0.0005, max_pulse_width=0.0024, pin_factory=factory)
servo2 = AngularServo(SERVO2_PIN, min_angle=0, max_angle=180, min_pulse_width=0.0005, max_pulse_width=0.0024, pin_factory=factory)

# Servo position tracking (0-180 degrees, start at 90 = center)
servo1_position = 90
servo2_position = 90

# Set servos to center position
servo1.angle = servo1_position
servo2.angle = servo2_position
time.sleep(0.5)  # Allow servos to move to center

stby.off()  # Initially in standby

status = {'state': 'Stopped', 'speed': 0}

@socketio.on('motor_command')
def handle_motor_command(data):
    # data should be a dict: { 'a': int, 'b': int }
    try:
        a = int(data.get('a', 0))
        b = int(data.get('b', 0))
    except (ValueError, TypeError):
        emit('motor_status', {'error': 'Invalid motor values'})
        return
    a = max(-100, min(100, a))
    b = max(-100, min(100, b))
    pwmA.value = abs(a) / 100.0
    pwmB.value = abs(b) / 100.0
    # Set direction based on sign
    if a > 0:
        ain1.on()
        ain2.off()
    elif a < 0:
        ain1.off()
        ain2.on()
    else:
        ain1.off()
        ain2.off()
    if b > 0:
        bin1.on()
        bin2.off()
    elif b < 0:
        bin1.off()
        bin2.on()
    else:
        bin1.off()
        bin2.off()
    stby.on() if (a != 0 or b != 0) else stby.off()
    status['state'] = f"Motors: A={a} B={b}"
    status['speed'] = f"A={a} B={b}"
    emit('motor_status', status)

@socketio.on('stop_command')
def handle_stop_command():
    pwmA.value = 0
    pwmB.value = 0
    ain1.off()
    ain2.off()
    bin1.off()
    bin2.off()
    stby.off()
    status['state'] = 'Stopped'
    status['speed'] = 'A=0 B=0'
    emit('motor_status', status)

@socketio.on('camera_command')
def handle_camera_command(data):
    """Handle relative camera movement commands - only update when there's actual input"""
    global servo1_position, servo2_position
    try:
        pan_delta = float(data.get('pan', 0))  # Horizontal movement
        tilt_delta = float(data.get('tilt', 0))  # Vertical movement
    except (ValueError, TypeError):
        return
    
    # Only process if there's actual movement (avoid jitter from noise)
    if abs(pan_delta) < 0.01 and abs(tilt_delta) < 0.01:
        return
    
    # Update positions with very slow movement (small increments)
    CAMERA_SPEED = 0.1  # Degrees per update - slow to prevent over-correction
    servo1_position += pan_delta * CAMERA_SPEED
    servo2_position += tilt_delta * CAMERA_SPEED
    
    # Clamp to 0-180 degree range
    servo1_position = max(0, min(180, servo1_position))
    servo2_position = max(0, min(180, servo2_position))
    
    # Set servo positions using GPIO Zero (handles PWM properly)
    servo1.angle = servo1_position
    servo2.angle = servo2_position

@app.route('/status')
def get_status():
    return status

@app.route('/')
def index():
    return send_file('autko.html')

WIDTH = 640
HEIGHT = 480

rotation_header = bytes()
WIDTH, HEIGHT = HEIGHT, WIDTH
code = 3 # Rotate 180 degrees
exif_bytes = piexif.dump({'0th': {piexif.ImageIFD.Orientation: code}})
exif_len = len(exif_bytes) + 2
rotation_header = bytes.fromhex('ffe1') + exif_len.to_bytes(2, 'big') + exif_bytes

class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf[:2] + rotation_header + buf[2:]
            self.condition.notify_all()

# Global camera and output
picam2 = None
output = None

def start_camera():
    global picam2, output
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
    output = StreamingOutput()
    picam2.start_recording(MJPEGEncoder(), FileOutput(output))

# Start camera in a background thread on app startup
camera_thread = threading.Thread(target=start_camera)
camera_thread.daemon = True
camera_thread.start()

@app.route('/mjpeg')
def mjpeg_stream():
    def generate():
        while True:
            with output.condition:
                output.condition.wait()
                frame = output.frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n'
                   b'Content-Length: ' + f"{len(frame)}".encode() + b'\r\n\r\n' + frame + b'\r\n')
            time.sleep(1/30)  # Limit to 30 FPS
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=25565)
