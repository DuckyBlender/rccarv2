import RPi.GPIO as GPIO
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

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(PWMA, GPIO.OUT)
GPIO.setup(PWMB, GPIO.OUT)
GPIO.setup(AIN1, GPIO.OUT)
GPIO.setup(AIN2, GPIO.OUT)
GPIO.setup(STBY, GPIO.OUT)
GPIO.setup(BIN1, GPIO.OUT)
GPIO.setup(BIN2, GPIO.OUT)
GPIO.setup(SERVO1_PIN, GPIO.OUT)
GPIO.setup(SERVO2_PIN, GPIO.OUT)

# Initialize PWM
pwmA = GPIO.PWM(PWMA, 100)
pwmB = GPIO.PWM(PWMB, 100)
pwmA.start(0)
pwmB.start(0)

# Initialize servo PWM (50Hz for servos)
servo1 = GPIO.PWM(SERVO1_PIN, 50)
servo2 = GPIO.PWM(SERVO2_PIN, 50)
servo1.start(0)
servo2.start(0)

# Servo position tracking (0-180 degrees, start at 90 = center)
servo1_position = 90
servo2_position = 90

# Set servos to center position (7.5% duty cycle = 90 degrees)
def set_servo_angle(pwm, angle):
    """Set servo angle (0-180 degrees) and maintain position with continuous PWM"""
    angle = max(0, min(180, angle))
    duty_cycle = 2.5 + (angle / 180.0) * 10.0  # 2.5% to 12.5%
    pwm.ChangeDutyCycle(duty_cycle)

set_servo_angle(servo1, servo1_position)
set_servo_angle(servo2, servo2_position)
time.sleep(0.5)  # Allow servos to move to center
# Keep PWM running to maintain position

GPIO.output(STBY, GPIO.LOW)  # Initially in standby

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
    pwmA.ChangeDutyCycle(abs(a))
    pwmB.ChangeDutyCycle(abs(b))
    # Set direction based on sign
    if a > 0:
        GPIO.output(AIN1, GPIO.HIGH)
        GPIO.output(AIN2, GPIO.LOW)
    elif a < 0:
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.HIGH)
    else:
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.LOW)
    if b > 0:
        GPIO.output(BIN1, GPIO.HIGH)
        GPIO.output(BIN2, GPIO.LOW)
    elif b < 0:
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.HIGH)
    else:
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.LOW)
    GPIO.output(STBY, GPIO.HIGH if (a != 0 or b != 0) else GPIO.LOW)
    status['state'] = f"Motors: A={a} B={b}"
    status['speed'] = f"A={a} B={b}"
    emit('motor_status', status)

@socketio.on('stop_command')
def handle_stop_command():
    pwmA.ChangeDutyCycle(0)
    pwmB.ChangeDutyCycle(0)
    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.LOW)
    GPIO.output(BIN2, GPIO.LOW)
    GPIO.output(STBY, GPIO.LOW)
    status['state'] = 'Stopped'
    status['speed'] = 'A=0 B=0'
    emit('motor_status', status)

@socketio.on('camera_command')
def handle_camera_command(data):
    """Handle relative camera movement commands"""
    global servo1_position, servo2_position
    try:
        pan_delta = float(data.get('pan', 0))  # Horizontal movement
        tilt_delta = float(data.get('tilt', 0))  # Vertical movement
    except (ValueError, TypeError):
        return
    
    # Update positions with very slow movement (small increments)
    CAMERA_SPEED = 0.2  # Degrees per update - very slow
    servo1_position += pan_delta * CAMERA_SPEED
    servo2_position += tilt_delta * CAMERA_SPEED
    
    # Clamp to 0-180 degree range
    servo1_position = max(0, min(180, servo1_position))
    servo2_position = max(0, min(180, servo2_position))
    
    # Set servo positions and maintain with continuous PWM
    set_servo_angle(servo1, servo1_position)
    set_servo_angle(servo2, servo2_position)

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
