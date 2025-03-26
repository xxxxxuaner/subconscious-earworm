import machine
from machine import I2S, Pin
import time
import os
import uos

print("=== Microphone Test Script ===")

# Initialize SD card
def init_sd():
    print("Initializing SD card...")
    try:
        sd = machine.SDCard(slot=3, width=1,
                        sck=machine.Pin(7),
                        mosi=machine.Pin(9),
                        miso=machine.Pin(8),
                        cs=machine.Pin(21))
        
        # Mount the SD card
        try:
            uos.mount(sd, '/sd')
        except OSError:
            # Already mounted - unmount and remount
            try:
                uos.umount('/sd')
                time.sleep(0.1)
                uos.mount(sd, '/sd')
            except:
                pass
                
        print("SD card mounted successfully")
        print("SD contents:", os.listdir('/sd'))
        return sd
    except Exception as e:
        print("ERROR: SD card initialization failed:", e)
        raise

# Initialize microphone
def init_mic():
    print("Initializing microphone...")
    return I2S(
        0,
        ws=Pin(1),
        sd=Pin(2),
        sck=Pin(3),
        mode=I2S.RX,
        bits=16,
        format=I2S.MONO,
        rate=16000,
        ibuf=4000
    )

# Initialize speaker
def init_speaker():
    print("Initializing speaker...")
    return I2S(
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

def record_to_file(filename, duration_seconds=3, gain=5):
    print(f"Recording for {duration_seconds} seconds directly to {filename} (gain={gain}x)...")
    
    # Calculate number of samples
    samples_per_second = 16000  # Our sample rate
    total_samples = samples_per_second * duration_seconds
    samples_recorded = 0
    
    try:
        with open(f'/sd/{filename}', 'wb') as f:
            # Record in chunks
            while samples_recorded < total_samples * 2:  # *2 because each sample is 2 bytes
                buffer = bytearray(1024)  # 512 samples per chunk
                mic.readinto(buffer)
                
                # Apply gain to the samples
                # Convert bytearray to array of 16-bit samples
                amplified = bytearray(len(buffer))
                for i in range(0, len(buffer), 2):
                    # Get 16-bit sample
                    sample = (buffer[i+1] << 8) | buffer[i]
                    if sample & 0x8000:  # Convert to signed
                        sample -= 0x10000
                    
                    # Apply gain and clamp to 16-bit range
                    sample = int(sample * gain)
                    sample = max(min(sample, 32767), -32768)
                    
                    # Convert back to bytes
                    amplified[i] = sample & 0xFF
                    amplified[i+1] = (sample >> 8) & 0xFF
                
                # Write amplified data
                f.write(amplified)
                samples_recorded += len(buffer)
                
                # Print progress
                progress = (samples_recorded / (total_samples * 2)) * 100
                print(f"Recording progress: {progress:.1f}%")
        
        print("Recording complete!")
        return True
        
    except Exception as e:
        print("Error during recording:", e)
        return False

def play_from_file(filename):
    print(f"Playing audio from {filename}...")
    try:
        with open(f'/sd/{filename}', 'rb') as f:
            # Read and play in chunks
            while True:
                chunk = f.read(1024)  # Read 1KB at a time
                if not chunk:
                    break
                    
                speaker.write(chunk)
                
        print("Playback complete!")
        return True
        
    except Exception as e:
        print("Error during playback:", e)
        return False

# Main test sequence
try:
    # Initialize hardware
    sd = init_sd()
    mic = init_mic()
    speaker = init_speaker()
    
    print("\nStarting test sequence...")
    
    # Record audio directly to file with gain
    print("\n1. Recording audio to SD card...")
    if record_to_file('mic_test.raw', duration_seconds=3, gain=5):  # 5x gain
        
        # Play it back from the file
        print("\n2. Playing back recording from SD card...")
        play_from_file('mic_test.raw')
    
    print("\nTest sequence complete!")

except Exception as e:
    print("Error in test sequence:", e)
    import sys
    sys.print_exception(e)  # Print full traceback

finally:
    # Cleanup
    try:
        mic.deinit()
        speaker.deinit()
        uos.umount('/sd')
        print("Cleanup complete")
    except:
        pass 