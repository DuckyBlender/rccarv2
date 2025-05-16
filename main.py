import RPi.GPIO as GPIO
from flask import Flask, make_response, send_file, Response
import threading
import time
import cv2
import io
import piexif
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

app = Flask(__name__)

# Define GPIO pins
PWMA = 12
PWMB = 13
AIN1 = 3
AIN2 = 2
STBY = 4
BIN1 = 20
BIN2 = 21

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(PWMA, GPIO.OUT)
GPIO.setup(PWMB, GPIO.OUT)
GPIO.setup(AIN1, GPIO.OUT)
GPIO.setup(AIN2, GPIO.OUT)
GPIO.setup(STBY, GPIO.OUT)
GPIO.setup(BIN1, GPIO.OUT)
GPIO.setup(BIN2, GPIO.OUT)

# Initialize PWM
pwmA = GPIO.PWM(PWMA, 100)
pwmB = GPIO.PWM(PWMB, 100)
pwmA.start(0)
pwmB.start(0)

GPIO.output(STBY, GPIO.LOW)  # Initially in standby

status = {'state': 'Stopped', 'speed': 0}

def set_motor_directions(direction):
    if direction == 'forward':
        GPIO.output(AIN1, GPIO.HIGH)
        GPIO.output(AIN2, GPIO.LOW)
        GPIO.output(BIN1, GPIO.HIGH)
        GPIO.output(BIN2, GPIO.LOW)
    elif direction == 'backward':
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.HIGH)
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.HIGH)
    elif direction == 'left':
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.HIGH)
        GPIO.output(BIN1, GPIO.HIGH)
        GPIO.output(BIN2, GPIO.LOW)
    elif direction == 'right':
        GPIO.output(AIN1, GPIO.HIGH)
        GPIO.output(AIN2, GPIO.LOW)
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.HIGH)
    else:  # stop
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.LOW)
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.LOW)

@app.route('/spinleft/<int:speed>')
def spinleft(speed):
    # Left spin: left motor backward, right motor forward
    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.HIGH)
    GPIO.output(BIN1, GPIO.HIGH)
    GPIO.output(BIN2, GPIO.LOW)
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(speed)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Spin Left'
    status['speed'] = speed
    return status

@app.route('/spinright/<int:speed>')
def spinright(speed):
    # Right spin: left motor forward, right motor backward
    GPIO.output(AIN1, GPIO.HIGH)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.LOW)
    GPIO.output(BIN2, GPIO.HIGH)
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(speed)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Spin Right'
    status['speed'] = speed
    return status

@app.route('/forward/<int:speed>')
def forward(speed):
    set_motor_directions('forward')
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(speed)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Forward'
    status['speed'] = speed
    return status

@app.route('/backward/<int:speed>')
def backward(speed):
    set_motor_directions('backward')
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(speed)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Backward'
    status['speed'] = speed
    return status

@app.route('/left/<int:speed>')
def left(speed):
    # Only run right motor forward for left turn
    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.HIGH)
    GPIO.output(BIN2, GPIO.LOW)
    pwmA.ChangeDutyCycle(0)
    pwmB.ChangeDutyCycle(speed)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Left'
    status['speed'] = speed
    return status

@app.route('/right/<int:speed>')
def right(speed):
    # Only run left motor forward for right turn
    GPIO.output(AIN1, GPIO.HIGH)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.LOW)
    GPIO.output(BIN2, GPIO.LOW)
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(0)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Right'
    status['speed'] = speed
    return status

@app.route('/stop')
def stop():
    set_motor_directions('stop')
    pwmA.ChangeDutyCycle(0)
    pwmB.ChangeDutyCycle(0)
    GPIO.output(STBY, GPIO.LOW)
    status['state'] = 'Stopped'
    status['speed'] = 0
    return status

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
    app.run(host='0.0.0.0', port=5000)