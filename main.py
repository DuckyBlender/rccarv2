import RPi.GPIO as GPIO
import time

# Motor pins (BCM)
PWMA = 12
AIN1 = 3
AIN2 = 2
PWMB = 13
BIN1 = 20
BIN2 = 21
STBY = 4

PWM_FREQ = 500

pwm_a = None
pwm_b = None
driver_active = False

def setup():
    global pwm_a, pwm_b
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # Setup motor pins
    GPIO.setup(PWMA, GPIO.OUT)
    GPIO.setup(AIN1, GPIO.OUT)
    GPIO.setup(AIN2, GPIO.OUT)
    GPIO.setup(PWMB, GPIO.OUT)
    GPIO.setup(BIN1, GPIO.OUT)
    GPIO.setup(BIN2, GPIO.OUT)
    GPIO.setup(STBY, GPIO.OUT)

    # Initialize pins
    GPIO.output(STBY, GPIO.LOW)
    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.LOW)
    GPIO.output(BIN2, GPIO.LOW)

    # Setup PWM
    pwm_a = GPIO.PWM(PWMA, PWM_FREQ)
    pwm_b = GPIO.PWM(PWMB, PWM_FREQ)
    pwm_a.start(0)
    pwm_b.start(0)

    print("Setup complete. Use commands like: left 50 2, right 30 1, forward 50 3, back 40 2")

def activate_driver():
    global driver_active
    GPIO.output(STBY, GPIO.HIGH)
    driver_active = True
    print("Driver activated.")

def deactivate_driver():
    global driver_active
    GPIO.output(STBY, GPIO.LOW)
    driver_active = False
    print("Driver in standby. Motors stopped.")

def move_motor(pin1, pin2, speed):
    if speed > 0:
        GPIO.output(pin1, GPIO.HIGH)
        GPIO.output(pin2, GPIO.LOW)
    elif speed < 0:
        GPIO.output(pin1, GPIO.LOW)
        GPIO.output(pin2, GPIO.HIGH)
    else:
        GPIO.output(pin1, GPIO.LOW)
        GPIO.output(pin2, GPIO.LOW)
    duty = abs(speed)
    if duty > 100:
        duty = 100
    pwm = pwm_a if (pin1 == AIN1 or pin1 == AIN2) else pwm_b
    pwm.ChangeDutyCycle(duty)

def run_command(cmd):
    global driver_active
    parts = cmd.strip().split()
    if not parts:
        return True

    if parts[0] == "left" and len(parts) >= 3:
        power = int(parts[1])
        time_s = float(parts[2])
        if not driver_active:
            activate_driver()
        move_motor(AIN1, AIN2, power)
        time.sleep(time_s)
        move_motor(AIN1, AIN2, 0)
        return True

    elif parts[0] == "right" and len(parts) >= 3:
        power = int(parts[1])
        time_s = float(parts[2])
        if not driver_active:
            activate_driver()
        move_motor(BIN1, BIN2, power)
        time.sleep(time_s)
        move_motor(BIN1, BIN2, 0)
        return True

    elif parts[0] == "forward" and len(parts) >= 3:
        power = int(parts[1])
        time_s = float(parts[2])
        if not driver_active:
            activate_driver()
        move_motor(AIN1, AIN2, power)
        move_motor(BIN1, BIN2, power)
        time.sleep(time_s)
        move_motor(AIN1, AIN2, 0)
        move_motor(BIN1, BIN2, 0)
        return True

    elif parts[0] == "back" and len(parts) >= 3:
        power = int(parts[1])
        time_s = float(parts[2])
        if not driver_active:
            activate_driver()
        move_motor(AIN1, AIN2, -power)
        move_motor(BIN1, BIN2, -power)
        time.sleep(time_s)
        move_motor(AIN1, AIN2, 0)
        move_motor(BIN1, BIN2, 0)
        return True

    elif parts[0] == "stop":
        move_motor(AIN1, AIN2, 0)
        move_motor(BIN1, BIN2, 0)
        return True

    elif parts[0] == "exit" or parts[0] == "quit":
        print("Exiting...")
        deactivate_driver()
        return False

    else:
        print("Invalid command. Use: left, right, forward, back, stop, exit")
        return True

def cleanup():
    global pwm_a, pwm_b
    if pwm_a:
        pwm_a.stop()
    if pwm_b:
        pwm_b.stop()
    GPIO.cleanup()
    print("Cleanup done.")

if __name__ == "__main__":
    setup()
    try:
        while True:
            cmd = input("Enter command: ").strip()
            if not run_command(cmd):
                break
    except KeyboardInterrupt:
        print("Interrupted.")
    finally:
        cleanup()