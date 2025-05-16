#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# Define GPIO pin numbers using BCM numbering
# Motor A
PWMA = 12  # PWM Speed Control
AIN2 = 2   # Direction Control 1
AIN1 = 3   # Direction Control 2

# Motor B
PWMB = 13  # PWM Speed Control
BIN2 = 21  # Direction Control 1
BIN1 = 20  # Direction Control 2

# Standby Pin
STBY = 4   # Driver Enable (HIGH = Active, LOW = Standby)

# PWM Configuration
PWM_FREQ = 500  # Hz - Adjust as needed

# Global PWM objects
pwm_a = None
pwm_b = None

def setup():
    """Initializes GPIO pins and PWM."""
    global pwm_a, pwm_b

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    GPIO.setup(PWMA, GPIO.OUT)
    GPIO.setup(AIN1, GPIO.OUT)
    GPIO.setup(AIN2, GPIO.OUT)

    GPIO.setup(PWMB, GPIO.OUT)
    GPIO.setup(BIN1, GPIO.OUT)
    GPIO.setup(BIN2, GPIO.OUT)

    GPIO.setup(STBY, GPIO.OUT)

    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.LOW)
    GPIO.output(BIN2, GPIO.LOW)
    GPIO.output(STBY, GPIO.LOW)

    pwm_a = GPIO.PWM(PWMA, PWM_FREQ)
    pwm_b = GPIO.PWM(PWMB, PWM_FREQ)

    pwm_a.start(0)
    pwm_b.start(0)

    print("GPIO and PWM setup complete.")
    print("Motor driver initially in Standby.")

def set_motor_a_speed(speed):
    """Sets speed for Motor A. Speed: -100 (backward) to 100 (forward). 0 is stop (coast)."""
    if not (-100 <= speed <= 100):
        print("Motor A: Speed must be between -100 and 100.")
        return

    if speed == 0:
        # Stop Motor A (coast/freewheel - no strong brake)
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.LOW)
        pwm_a.ChangeDutyCycle(0)
        print("Motor A: Stopped (Coast)")
    elif speed > 0:
        # Forward Motor A
        GPIO.output(AIN1, GPIO.HIGH)
        GPIO.output(AIN2, GPIO.LOW)
        pwm_a.ChangeDutyCycle(speed)
        print(f"Motor A: Forward {speed}%")
    else: # speed < 0
        # Backward Motor A
        GPIO.output(AIN1, GPIO.LOW)
        GPIO.output(AIN2, GPIO.HIGH)
        pwm_a.ChangeDutyCycle(abs(speed)) # Duty cycle is always positive
        print(f"Motor A: Backward {abs(speed)}%")

def set_motor_b_speed(speed):
    """Sets speed for Motor B. Speed: -100 (backward) to 100 (forward). 0 is stop (coast)."""
    if not (-100 <= speed <= 100):
        print("Motor B: Speed must be between -100 and 100.")
        return

    if speed == 0:
        # Stop Motor B (coast/freewheel - no strong brake)
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.LOW)
        pwm_b.ChangeDutyCycle(0)
        print("Motor B: Stopped (Coast)")
    elif speed > 0:
        # Forward Motor B
        GPIO.output(BIN1, GPIO.HIGH)
        GPIO.output(BIN2, GPIO.LOW)
        pwm_b.ChangeDutyCycle(speed)
        print(f"Motor B: Forward {speed}%")
    else: # speed < 0
        # Backward Motor B
        GPIO.output(BIN1, GPIO.LOW)
        GPIO.output(BIN2, GPIO.HIGH)
        pwm_b.ChangeDutyCycle(abs(speed)) # Duty cycle is always positive
        print(f"Motor B: Backward {abs(speed)}%")

def standby(active):
    """Controls the STBY pin."""
    if active:
        GPIO.output(STBY, GPIO.HIGH)
        print("Driver Activated.")
    else:
        GPIO.output(STBY, GPIO.LOW)
        # Ensure motors are stopped if going to standby
        set_motor_a_speed(0)
        set_motor_b_speed(0)
        print("Driver in Standby. Motors stopped.")

def cleanup():
    """Stops motors, cleans up GPIO resources."""
    global pwm_a, pwm_b
    print("\nCleaning up GPIO...")
    if pwm_a:
        pwm_a.stop()
    if pwm_b:
        pwm_b.stop()
    GPIO.output(AIN1, GPIO.LOW)
    GPIO.output(AIN2, GPIO.LOW)
    GPIO.output(BIN1, GPIO.LOW)
    GPIO.output(BIN2, GPIO.LOW)
    GPIO.output(STBY, GPIO.LOW)
    GPIO.cleanup()
    print("GPIO Cleanup Done.")

def print_instructions():
    print("\n--- Motor Control ---")
    print("Commands:")
    print("  a [speed]  : Set Motor A speed (-100 to 100). e.g., 'a 50', 'a -30', 'a 0'")
    print("  b [speed]  : Set Motor B speed (-100 to 100). e.g., 'b 75', 'b -100', 'b 0'")
    print("  on         : Activate motor driver (take out of standby)")
    print("  off        : Deactivate motor driver (put into standby, stops motors)")
    print("  stop       : Stop both motors (coast)")
    print("  help       : Show this help message")
    print("  quit / q   : Exit program")
    print("---------------------\n")

# --- Main Program ---
if __name__ == "__main__":
    try:
        setup()
        print_instructions()
        driver_active = False # Start with driver in standby

        while True:
            try:
                command = input("Enter command: ").strip().lower()
                parts = command.split()

                if not parts:
                    continue

                action = parts[0]

                if action in ["quit", "q"]:
                    print("Exiting program.")
                    break
                elif action == "help":
                    print_instructions()
                elif action == "on":
                    standby(True)
                    driver_active = True
                elif action == "off":
                    standby(False)
                    driver_active = False
                elif action == "stop":
                    if driver_active:
                        set_motor_a_speed(0)
                        set_motor_b_speed(0)
                    else:
                        print("Driver is in standby. Activate with 'on' first.")
                elif action == "a" and len(parts) == 2:
                    if not driver_active:
                        print("Driver is in standby. Activate with 'on' first.")
                        continue
                    try:
                        speed = int(parts[1])
                        set_motor_a_speed(speed)
                    except ValueError:
                        print("Invalid speed. Must be an integer.")
                elif action == "b" and len(parts) == 2:
                    if not driver_active:
                        print("Driver is in standby. Activate with 'on' first.")
                        continue
                    try:
                        speed = int(parts[1])
                        set_motor_b_speed(speed)
                    except ValueError:
                        print("Invalid speed. Must be an integer.")
                else:
                    print("Invalid command. Type 'help' for options.")

            except EOFError: # Handles Ctrl+D
                print("\nExiting program (EOF).")
                break
            except Exception as e_inner: # Catch errors within the loop to keep running
                print(f"Error during command processing: {e_inner}")


    except KeyboardInterrupt:
        print("\nCtrl+C detected. Stopping motors and exiting.")
    except Exception as e_outer:
        print(f"\nAn critical error occurred: {e_outer}")
    finally:
        if 'driver_active' in locals() and driver_active: # Check if defined
             standby(False) # Ensure driver is in standby before cleanup if it was active
        cleanup()
