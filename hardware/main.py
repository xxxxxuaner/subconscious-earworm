import machine
from machine import I2S, Pin
import time
import math
import os
import uos
import _thread

print("=== Ambient Sound Monitor - Initializing ===")

# Global variables
last_readings = [0] * 3
audio_playing = False
audio_should_play = False
audio_paused = False
lock = _thread.allocate_lock()
mic = None
audio = None
running = True  # Main control flag
rms_history = []
RMS_HISTORY_SIZE = 10  # For display and general tracking

# These will track consistent trigger states
above_threshold_count = 0  # Count of consecutive samples above threshold
below_threshold_count = 0  # Count of consecutive samples below threshold
ABOVE_THRESHOLD_REQUIRED = 50  # ~2 seconds worth of samples
BELOW_THRESHOLD_REQUIRED = 1   # ~1 second worth of samples

# ===== INITIALIZATION FUNCTIONS =====

def init_sd_card():
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

def init_mic():
    print("Initializing microphone...")
    try:
# Set up I2S for the microphone
        microphone = I2S(
    0,  # I2S ID
            ws=Pin(1), 
            sd=Pin(2), 
            sck=Pin(3),
    mode=I2S.RX,
    bits=16,
    format=I2S.MONO,
            rate=16000,
            ibuf=4000
        )
        print("Microphone initialized successfully")
        return microphone
    except Exception as e:
        print("ERROR: Microphone initialization failed:", e)
        raise

def init_speaker():
    print("Initializing speaker...")
    try:
        speaker = I2S(
            1,
            ws=Pin(6), #lrclr
            sck=Pin(5), #bclk
            sd=Pin(4), #dout
            mode=I2S.TX,
            bits=16,
            format=I2S.MONO,
            rate=16000,
            ibuf=4000
        )
        print("Speaker initialized successfully")
        return speaker
    except Exception as e:
        print("ERROR: Speaker initialization failed:", e)
        raise

# Safe cleanup function
def safe_cleanup():
    global mic, audio, running, audio_should_play, audio_playing
    print("Performing safe cleanup...")
    
    # Stop all threads
    running = False
    audio_should_play = False
    audio_playing = False
    
    # Wait for threads to stop
    time.sleep(1)
    
    # Cleanup hardware
    try:
        if mic:
            mic.deinit()
            print("Microphone deinitialized")
    except:
        pass
        
    try:
        if audio:
            audio.deinit()
            print("Speaker deinitialized")
    except:
        pass
        
    # Unmount SD card
    try:
        uos.umount('/sd')
        print("SD card unmounted")
    except:
        pass
    
    print("Cleanup complete")

# ===== SOUND DETECTION =====

def detect_sound():
    global mic, last_readings, running, rms_history
    
    if not running:
        return 0, 0
        
    try:
        # Read audio buffer
        buf = bytearray(2048)
        mic.readinto(buf)
        
        # Process samples with gain
        samples = []
        gain = 5  # Same gain as mic_test.py
        for i in range(0, len(buf), 2):
            # Get 16-bit sample
            value = (buf[i+1] << 8) | buf[i]
            if value & 0x8000:
                value -= 0x10000
            
            # Apply gain and clamp
            value = int(value * gain)
            value = max(min(value, 32767), -32768)
            
            samples.append(value)
        
        # Calculate RMS value
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        
        # Dynamic scaling
        min_rms = 3550
        max_rms = 4100
        
        # Calculate normalized level with logarithmic scaling
        if rms < min_rms:
            normalized_level = 0
        elif rms > max_rms:
            normalized_level = 100
        else:
            normalized_rms = (rms - min_rms) / (max_rms - min_rms)
            normalized_level = (math.log(1 + 9 * normalized_rms) / math.log(10)) * 100
        
        # Display counter information
        print(f"Sound: {normalized_level:.1f}% | RMS: {rms:.1f} | Above: {above_threshold_count}/{ABOVE_THRESHOLD_REQUIRED} | Below: {below_threshold_count}/{BELOW_THRESHOLD_REQUIRED}")
        
        return normalized_level, rms
        
    except Exception as e:
        print("ERROR in detect_sound:", e)
        try:
            if mic:
                mic.deinit()
            time.sleep(0.1)
            mic = init_mic()
        except:
            print("Failed to reinitialize mic")
        return 0, 0

# ===== AUDIO PLAYBACK =====
def play_audio_thread(filename):
    global audio_playing, audio_should_play, audio_paused, audio, running
    
    try:
        print(f"Audio thread starting for {filename}")
        while audio_should_play and running:
            try:
                with open('/sd/' + filename, 'rb') as f:
                    while audio_should_play and running:
                        if not audio_paused:
                            chunk = f.read(1024)
                            if not chunk:  # End of file
                                break  # Will restart from beginning
                            try:
                                audio.write(chunk)
                                # Small yield to allow other operations
                                time.sleep(0.001)
                            except Exception as e:
                                print(f"ERROR writing audio: {e}")
                                break
                        else:
                            time.sleep(0.1)  # Pause
                    
                    if not audio_should_play or not running:
                        break
            except Exception as e:
                print(f"ERROR opening audio file: {e}")
                break
    except Exception as e:
        print(f"ERROR in audio playback thread: {e}")
    finally:
        # Thorough cleanup
        with lock:
            audio_playing = False
            audio_should_play = False
            audio_paused = False
        try:
            # Reset audio interface if needed
            if audio and running:
                audio.deinit()
                time.sleep(0.1)
                audio = init_speaker()
        except:
            pass
        print("Audio thread ended and cleaned up")

def start_audio_playback(filename):
    global audio_playing, audio_should_play, audio_paused
    
    if not running:
        return
        
    with lock:
        if audio_playing:
            audio_paused = False
            print("Resuming playback")
            return
            
        audio_should_play = True
        audio_paused = False
        audio_playing = True
    
    print(f"Starting playback of {filename}")
    _thread.start_new_thread(play_audio_thread, (filename,))

def pause_audio_playback():
    global audio_paused, audio_playing
    
    if not running:
        return
        
    with lock:
        if audio_playing:
            audio_paused = True
            print("Paused playback")

# ===== ERROR WATCHDOG =====
def watchdog_thread():
    global running
    counter = 0
    
    # Give system time to initialize
    time.sleep(5)
    
    while running:
        counter += 1
        # Every 30 seconds, check if system is responsive
        if counter > 300:  # 300 * 0.1s = 30 seconds
            print("Watchdog check")
            counter = 0
            # Add any health checks here
        time.sleep(0.1)

# ===== MAIN PROGRAM =====

def main():
    global mic, audio, running, audio_playing, audio_paused, above_threshold_count, below_threshold_count
    
    # Set up watchdog thread for safety
    _thread.start_new_thread(watchdog_thread, ())
    
    print("\n=== Ambient Sound Monitor - Starting ===")
    
    # Configuration
    AUDIO_FILE = 'branches.raw'
    THRESHOLD_RMS = 1500
    
    # Verify audio file exists
    if AUDIO_FILE not in os.listdir('/sd'):
        print(f"ERROR: {AUDIO_FILE} not found on SD card!")
        print("Available files:", os.listdir('/sd'))
        return
    
    print(f"Using audio file: {AUDIO_FILE}")
    print(f"RMS threshold: {THRESHOLD_RMS}")
    
    try:
        print("Starting main monitoring loop")
        while running:
            try:
                level, rms = detect_sound()
                
                # Threshold checking with hysteresis
                if rms > THRESHOLD_RMS:
                    print(f"Sound level above threshold")
                    above_threshold_count += 1
                    below_threshold_count = 0  # Reset counter when above threshold
                    
                    # Only start playback after sustained noise
                    if above_threshold_count >= ABOVE_THRESHOLD_REQUIRED:
                        if not audio_playing or audio_paused:
                            print(f"🔊 SUSTAINED TRIGGER: RMS={rms:.1f}, Above for {above_threshold_count} samples")
                            start_audio_playback(AUDIO_FILE)
                else:
                    print(f"Sound level below threshold")
                    below_threshold_count += 1
                    above_threshold_count = 0  # Reset counter when below threshold
                    
                    # Quicker to pause after sound drops
                    if below_threshold_count >= BELOW_THRESHOLD_REQUIRED:
                        if audio_playing and not audio_paused:
                            print(f"🔇 SUSTAINED QUIET: RMS={rms:.1f}, Below for {below_threshold_count} samples")
                            pause_audio_playback()
            except Exception as e:
                print(f"ERROR in loop iteration: {e}")
                import sys
                sys.print_exception(e)  # Print full exception details
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"ERROR in main loop: {e}")
        import sys
        sys.print_exception(e)  # Print full exception details
    finally:
        # Set flag to stop all threads
        running = False
        
        # Thorough cleanup
        with lock:
            audio_should_play = False
            audio_playing = False
            audio_paused = False
        
        # Longer delay for cleanup
        time.sleep(1.0)  
        
        # Final hardware shutdown
        safe_cleanup()

# ===== SAFE BOOT DETECTION =====

# Allow interruption during boot
def safe_boot():
    print("Safe boot: Press any key in 5 seconds to enter REPL mode...")
    for i in range(50):
        print(".", end="")
        # Check for keypress (can't detect directly, but can add button check)
        time.sleep(0.1)
    print("\nContinuing with normal startup")

# ===== PROGRAM ENTRY POINT =====

try:
    # First thing: enable safe boot option
    safe_boot()
    
    # Sequential initialization with better error handling
    print("Initializing hardware components...")
    try:
        sd_card = init_sd_card()
        time.sleep(0.5)
        
        mic = init_mic()
        time.sleep(0.5)
        
        audio = init_speaker()
        time.sleep(0.5)
        
        print("All hardware initialized successfully")
        
        # Start main program
        main()
        
    except Exception as e:
        print("CRITICAL ERROR during initialization:", e)
        safe_cleanup()
        
except KeyboardInterrupt:
    # Catch keyboard interrupt during initialization
    print("\nStartup interrupted by user - entering REPL mode")
    # Don't start the program
    
finally:
    # Final cleanup if we get here
    safe_cleanup()
