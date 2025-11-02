from flask import Flask, send_file, Response
from flask_socketio import SocketIO, emit
import threading
import time
import io
import piexif
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput
from gpiozero import AngularServo, OutputDevice, PWMOutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory

app = Flask(__name__)
app.config["SECRET_KEY"] = "rccar_secret"
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    ping_timeout=10,
    ping_interval=5,
    logger=False,
    engineio_logger=False,
)

# GPIO Configuration
PWMA, PWMB = 12, 13
AIN1, AIN2 = 3, 2
BIN1, BIN2 = 20, 21
STBY = 4
SERVO1_PIN, SERVO2_PIN = 26, 6

# Initialize PiGPIO Factory
try:
    factory = PiGPIOFactory()
except Exception:
    factory = None

# Motor Controllers with higher PWM frequency for smoother control
if factory:
    pwmA = PWMOutputDevice(PWMA, pin_factory=factory, frequency=1000)
    pwmB = PWMOutputDevice(PWMB, pin_factory=factory, frequency=1000)
    ain1 = OutputDevice(AIN1, pin_factory=factory)
    ain2 = OutputDevice(AIN2, pin_factory=factory)
    bin1 = OutputDevice(BIN1, pin_factory=factory)
    bin2 = OutputDevice(BIN2, pin_factory=factory)
    stby = OutputDevice(STBY, pin_factory=factory)
else:
    pwmA = PWMOutputDevice(PWMA, frequency=1000)
    pwmB = PWMOutputDevice(PWMB, frequency=1000)
    ain1 = OutputDevice(AIN1)
    ain2 = OutputDevice(AIN2)
    bin1 = OutputDevice(BIN1)
    bin2 = OutputDevice(BIN2)
    stby = OutputDevice(STBY)

# Servo Controllers
servo1 = servo2 = None
servo1_position = servo2_position = 90

try:
    if factory:
        servo1 = AngularServo(
            SERVO1_PIN,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,
            max_pulse_width=0.0024,
            pin_factory=factory,
            initial_angle=90,
        )
        servo2 = AngularServo(
            SERVO2_PIN,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,
            max_pulse_width=0.0024,
            pin_factory=factory,
            initial_angle=90,
        )
    else:
        servo1 = AngularServo(
            SERVO1_PIN,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,
            max_pulse_width=0.0024,
            initial_angle=90,
        )
        servo2 = AngularServo(
            SERVO2_PIN,
            min_angle=0,
            max_angle=180,
            min_pulse_width=0.0005,
            max_pulse_width=0.0024,
            initial_angle=90,
        )
    time.sleep(0.3)
except Exception as e:
    print(f"Servo init error: {e}")

stby.off()

# Rate limiting with locks for thread safety
motor_lock = threading.Lock()
camera_lock = threading.Lock()
last_motor_time = 0
last_camera_time = 0
MOTOR_MIN_INTERVAL = 0.02  # 50Hz max
CAMERA_MIN_INTERVAL = 0.03  # 33Hz max

# Current state
current_motor = {"a": 0, "b": 0}


def set_motor(a, b):
    """Set motor speeds with direction control - optimized for speed"""
    a = max(-100, min(100, a))
    b = max(-100, min(100, b))

    pwmA.value = abs(a) / 100.0
    pwmB.value = abs(b) / 100.0

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
    current_motor["a"] = a
    current_motor["b"] = b


def set_camera(pan, tilt, speed):
    """Update camera position with deltas"""
    global servo1_position, servo2_position

    if not servo1 or not servo2:
        return

    servo1_position = max(0, min(180, servo1_position - tilt * speed))
    servo2_position = max(0, min(180, servo2_position - pan * speed))

    try:
        servo1.angle = servo1_position
        servo2.angle = servo2_position
    except Exception:
        pass


@socketio.on("connect")
def handle_connect():
    emit("motor_status", {"state": "Connected"})


@socketio.on("motor_command")
def handle_motor_command(data):
    global last_motor_time

    with motor_lock:
        now = time.time()
        if now - last_motor_time < MOTOR_MIN_INTERVAL:
            return
        last_motor_time = now

    try:
        a = int(data.get("a", 0))
        b = int(data.get("b", 0))
        set_motor(a, b)
    except (ValueError, TypeError):
        pass


@socketio.on("stop_command")
def handle_stop():
    set_motor(0, 0)


@socketio.on("camera_command")
def handle_camera(data):
    global last_camera_time, servo1_position, servo2_position

    with camera_lock:
        now = time.time()
        if now - last_camera_time < CAMERA_MIN_INTERVAL:
            return
        last_camera_time = now

    if data.get("center"):
        servo1_position = servo2_position = 90
        if servo1 and servo2:
            try:
                servo1.angle = 90
                servo2.angle = 90
            except Exception:
                pass
        return

    try:
        pan = float(data.get("pan", 0))
        tilt = float(data.get("tilt", 0))
        speed = max(2.0, min(10.0, float(data.get("speed", 5.0))))

        if abs(pan) > 0.01 or abs(tilt) > 0.01:
            set_camera(pan, tilt, speed)
    except (ValueError, TypeError):
        pass


@app.route("/status")
def get_status():
    return {
        "state": f"A:{current_motor['a']} B:{current_motor['b']}"
        if any(current_motor.values())
        else "Stopped",
        "speed": current_motor,
    }


@app.route("/")
def index():
    return send_file("autko.html")


# Camera Stream Setup
WIDTH, HEIGHT = 640, 480
rotation_header = bytes()
WIDTH, HEIGHT = HEIGHT, WIDTH
code = 3
exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Orientation: code}})
exif_len = len(exif_bytes) + 2
rotation_header = bytes.fromhex("ffe1") + exif_len.to_bytes(2, "big") + exif_bytes


class StreamingOutput(io.BufferedIOBase):
    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf[:2] + rotation_header + buf[2:]
            self.condition.notify_all()


picam2 = None
output = None


def start_camera():
    global picam2, output
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))
    output = StreamingOutput()
    picam2.start_recording(MJPEGEncoder(), FileOutput(output))


# Start camera in background thread
camera_thread = threading.Thread(target=start_camera, daemon=True)
camera_thread.start()


@app.route("/mjpeg")
def mjpeg_stream():
    def generate():
        while True:
            with output.condition:
                output.condition.wait()
                frame = output.frame
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: "
                + f"{len(frame)}".encode()
                + b"\r\n\r\n"
                + frame
                + b"\r\n"
            )
            time.sleep(0.033)  # ~30 FPS

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    print("Starting RC Car Server on port 25565...")
    socketio.run(
        app, host="0.0.0.0", port=25565, debug=False, allow_unsafe_werkzeug=True
    )
