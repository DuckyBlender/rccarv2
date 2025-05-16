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