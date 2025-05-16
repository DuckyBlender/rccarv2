import RPi.GPIO as GPIO
from flask import Flask, make_response
import threading
import time

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
    set_motor_directions('left')
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(speed)
    GPIO.output(STBY, GPIO.HIGH)
    status['state'] = 'Left'
    status['speed'] = speed
    return status

@app.route('/right/<int:speed>')
def right(speed):
    set_motor_directions('right')
    pwmA.ChangeDutyCycle(speed)
    pwmB.ChangeDutyCycle(speed)
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
    with open('index.html', 'r') as f:
        return f.read(), 200, {'Content-Type': 'text/html'}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

creamers@raspberrypi:~ $ ^C
creamers@raspberrypi:~ $ ls
autko  autko2  main2.py  main3.py  main4.py
creamers@raspberrypi:~ $ cat main4.py 
#!/usr/bin/python3

# This is the same as mjpeg_server_2.py, but allows 90 or 270 degree rotations.

import io
import logging
import socketserver
from http import server
from threading import Condition

import piexif

from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput

ROTATION = 270  # Use 0, 90 or 270
WIDTH = 640
HEIGHT = 480

rotation_header = bytes()
if ROTATION:
    WIDTH, HEIGHT = HEIGHT, WIDTH
    code = 6 if ROTATION == 90 else 8
    exif_bytes = piexif.dump({'0th': {piexif.ImageIFD.Orientation: code}})
    exif_len = len(exif_bytes) + 2
    rotation_header = bytes.fromhex('ffe1') + exif_len.to_bytes(2, 'big') + exif_bytes

PAGE = f"""\
<html>
<head>
<title>picamera2 MJPEG streaming demo</title>
</head>
<body>
<h1>Picamera2 MJPEG Streaming Demo</h1>
<img src="stream.mjpg" width="{WIDTH}" height="{HEIGHT}" />
</body>
</html>
"""


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf[:2] + rotation_header + buf[2:]
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
output = StreamingOutput()
picam2.start_recording(MJPEGEncoder(), FileOutput(output))

try:
    address = ('', 8000)
    server = StreamingServer(address, StreamingHandler)
    server.serve_forever()
finally:
    picam2.stop_recording()