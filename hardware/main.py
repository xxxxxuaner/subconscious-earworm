import network
from machine import I2S, Pin
import machine
import array
import time
import struct
from builtins import abs  # Explicitly import abs function
import math
import os
import uos


print("Hello World")
#exec(open('main.py').read())
#run micropython: https://wiki.seeedstudio.com/xiao_esp32s3_with_micropython/
#ls /dev/cu*
#esptool.py --chip esp32s3 --port /dev/cu.usbmodem2101 erase_flash
#esptool.py --chip esp32s3 --port /dev/cu.usbmodem2101 --baud 460800 write_flash -z 0x0 /Users/koiren/Desktop/subconscious_earworm/ESP32_GENERIC_S3-20241129-v1.24.1.bin


# SD card configuration
sd = machine.SDCard(slot=3, width=1,
                    sck=machine.Pin(7),
                    mosi=machine.Pin(9),
                    miso=machine.Pin(8),
                    cs=machine.Pin(21))

# Mount the SD card
uos.mount(sd, '/sd')

# Write a file
with open('/sd/hello.txt', 'w') as f:
    f.write('Hello, SD card!')

# Read the file
with open('/sd/hello.txt', 'r') as f:
    print(f.read())

# List SD contents
print(uos.listdir('/sd'))

def init_mic():
    # Deinit any existing I2S instance
    try:
        mic.deinit()
    except:
        pass
    
    # Set up I2S for the microphone
    return I2S(
        0,  # I2S ID
        ws=Pin(1),  # WS (Word Select / LRCLK)
        sd=Pin(2),  # DOUT (Data)
        sck=Pin(3),  # BCLK (Bit Clock)
        mode=I2S.RX,
        bits=16,
        format=I2S.MONO,
        rate=16000,  # 16kHz sample rate
        ibuf=2000    # Increased buffer size for better stability
    )

# Initialize the microphone
mic = init_mic()

def detect_sound():
    global mic
    try:
        # Read a larger buffer for better sampling
        buf = bytearray(1024)  # Increased buffer size for better accuracy
        mic.readinto(buf)
        
        # Calculate RMS (Root Mean Square) for better audio level measurement
        samples = []
        for i in range(0, len(buf), 2):
            value = (buf[i+1] << 8) | buf[i]
            if value & 0x8000:
                value -= 0x10000
            samples.append(value)
        
        # Calculate RMS value
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        
        # Scale RMS to a 0-100 range based on your environment
        # Very quiet: ~3600
        # Loud: ~4000
        # So we'll use 3600 as our baseline and 4000 as our maximum
        min_rms = 3600
        max_rms = 4000
        
        # Enhanced sensitivity for quieter sounds using exponential scaling
        if rms < min_rms:
            normalized_level = 0
        elif rms > max_rms:
            normalized_level = 100
        else:
            # Use exponential scaling to make it more sensitive to quieter sounds
            # This will give more resolution in the lower ranges
            range_rms = max_rms - min_rms
            normalized_rms = (rms - min_rms) / range_rms
            normalized_level = math.pow(normalized_rms, 0.5) * 100  # Square root for more sensitivity to lower values
        
        # Categorize the noise level based on normalized values
        # Adjusted boundaries to be more sensitive to quieter sounds
        if normalized_level < 5:
            category = "Very Quiet"
        elif normalized_level < 15:
            category = "Quiet"
        elif normalized_level < 30:
            category = "Moderate"
        elif normalized_level < 50:
            category = "Loud"
        else:
            category = "Very Loud"
        
        # Print detailed information
        print(f"Level: {normalized_level:.1f}/100 ({category})")
        print(f"Raw RMS: {rms:.1f}")
        
        # Return both the level and whether it's above threshold
        threshold = 5  # Very low threshold for maximum sensitivity
        return normalized_level, rms  # Now returning RMS value instead of threshold check
        
    except Exception as e:
        print("Error:", e)
        mic = init_mic()
        time.sleep(0.1)
        return 0, 0

print("Testing ambient noise detection with external microphone...")
print("Monitoring environment levels...")
print("Calibrated for RMS range: 3600 (Very Quiet) - 4000 (Very Loud)")
print("Sensitivity: Ultra High (threshold at 5)")
print("Using exponential scaling for better quiet sound detection")

# Initialize variables for running average
WINDOW_SIZE = 5  # Smaller window for faster response
readings = []

# try:
#     while True:
#         level, rms = detect_sound()  # Now getting RMS value
        
#         # Maintain a running average
#         readings.append(level)
#         if len(readings) > WINDOW_SIZE:
#             readings.pop(0)
        
#         avg_level = sum(readings) / len(readings)
        
#         # Print a visual indicator of the noise level
#         bars = "█" * int(avg_level / 5)
#         print(f"Level: {bars} ({avg_level:.1f})")
        
#         time.sleep(0.2)  # Slightly longer delay for more stable readings
# except KeyboardInterrupt:
#     print("\nMonitoring stopped")
#     mic.deinit()

# Set up I2S for DAC; debug the speaker
print("\nInitializing speaker...")
try:
    audio = I2S(
        1, #VIN → 3.3V ; GND → GND
        ws=Pin(6),   #LRC (LRCLK) → GPIO 9
        sck=Pin(5),  #BCLK → GPIO 8
        sd=Pin(4),   #DIN → GPIO 7
        mode=I2S.TX,
        bits=16,
        format=I2S.MONO,
        rate=16000,
        ibuf=4000
    )
    print("Speaker initialized successfully")
except Exception as e:
    print("Error initializing speaker:", e)
    raise

def play_audio(filename):
    try:
        print(f"Playing {filename} from SD card...")
        # Open the raw audio file from SD card
        with open('/sd/' + filename, 'rb') as f:
            # Read and play in chunks of 1024 bytes (512 samples)
            while True:
                chunk = f.read(1024)
                if not chunk:
                    break
                audio.write(chunk)
                time.sleep(0.01)  # Small delay to prevent buffer overflow
        print("Audio playback completed")
        
    except Exception as e:
        print(f"Error playing audio: {e}")
        print("Make sure the audio file is in raw format (16-bit mono PCM) and exists on the SD card")

def play_beep():
    try:
        print("Playing beep...")
        # Play the audio file
        play_audio('test1.raw')
        print("Beep finished!")
    except Exception as e:
        print("Error playing beep:", e)
        # Try to reinitialize the speaker
        try:
            audio.deinit()
            time.sleep(0.1)
            audio = I2S(
                1,
                ws=Pin(6),
                sck=Pin(5),
                sd=Pin(4),
                mode=I2S.TX,
                bits=16,
                format=I2S.MONO,
                rate=16000,
                ibuf=4000
            )
            print("Speaker reinitialized")
        except Exception as e2:
            print("Error reinitializing speaker:", e2)

# Test the speaker with a simple pattern
print("\nTesting speaker with a simple pattern...")
try:
    for i in range(3):
        print(f"Test beep {i+1}/3")
        play_beep()
        time.sleep(1)  # Wait between beeps
    print("Speaker test complete")
except Exception as e:
    print("Error during speaker test:", e)

# Main noise detection and beep loop
print("\nStarting noise-activated beeper...")
print("Will beep when RMS > 3800")

try:
    while True:
        level, rms = detect_sound()
        
        # Check if RMS is above threshold and beep if it is
        if rms > 3800:
            print("Loud noise detected! 🔊")
            play_beep()
        
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\nMonitoring stopped")
    mic.deinit()
    audio.deinit()
    # Unmount SD card before exiting
    try:
        os.umount('/sd')
        print("SD Card unmounted")
    except:
        pass

# # Test the speaker
# while True:
#     play_beep()  # Play a beep
#     time.sleep(1)  # Wait 1 second between beeps





# # connect to the internet
# def do_connect():
#     wlan = network.WLAN(network.STA_IF)  # Set up as station (client)
#     wlan.active(True)  # Activate WiFi
    
#     if not wlan.isconnected():
#         print('Connecting to network...')
#         wlan.connect('SSID', 'PASSWORD')  # Replace with correct SSID & Password
        
#         timeout = 10  # Set a timeout to avoid infinite loop
#         while not wlan.isconnected() and timeout > 0:
#             timeout -= 1
            
#     if wlan.isconnected():
#         print('Network config:', wlan.ifconfig())
#     else:
#         print('Failed to connect. Check SSID/Password.')
# do_connect()
