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

def record_to_file(filename, duration_seconds=3, apply_gain=False, gain=5, apply_correction=True):
    print(f"Recording for {duration_seconds} seconds directly to {filename}")
    print(f"Settings: gain={'ON' if apply_gain else 'OFF'} ({gain}x), "
          f"SPH0645LM4H correction: {'ON' if apply_correction else 'OFF'}")
    
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
                
                # Process samples
                amplified = bytearray(len(buffer))
                for i in range(0, len(buffer), 2):
                    # Get 16-bit sample
                    sample = (buffer[i+1] << 8) | buffer[i]
                    if sample & 0x8000:
                        sample -= 0x10000
                    
                    # Apply SPH0645LM4H correction if enabled
                    if apply_correction:
                        sample = sample >> 1
                    
                    # Apply gain if enabled
                    if apply_gain:
                        sample = int(sample * gain)
                    
                    # Clamp to 16-bit range
                    sample = max(min(sample, 32767), -32768)
                    
                    # Convert back to bytes
                    amplified[i] = sample & 0xFF
                    amplified[i+1] = (sample >> 8) & 0xFF
                
                # Write processed data
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

def int_to_binary_str(value, width=16):
    """Convert integer to binary string representation"""
    if value < 0:
        value = value & ((1 << width) - 1)  # Convert negative to two's complement
    result = ""
    for i in range(width-1, -1, -1):
        result += "1" if value & (1 << i) else "0"
    return result

def analyze_samples(filename, offset_seconds=1, num_samples=20):
    """Analyze samples from a specific point in the recording"""
    print(f"\nAnalyzing {filename} at {offset_seconds}s offset:")
    
    try:
        with open(f'/sd/{filename}', 'rb') as f:
            # Calculate offset in bytes (16000 samples/sec * 2 bytes/sample)
            offset_bytes = int(offset_seconds * 16000 * 2)
            f.seek(offset_bytes)
            
            # Read a chunk of samples
            data = f.read(num_samples * 2)  # 2 bytes per sample
            
            # Convert to samples and print
            samples = []
            for i in range(0, len(data), 2):
                sample = (data[i+1] << 8) | data[i]
                if sample & 0x8000:
                    sample -= 0x10000
                samples.append(sample)
            
            # Print analysis
            print("\nSample Analysis:")
            print("Index  |  Raw Value  |  Amplitude (%)  |  Binary")
            print("-" * 55)
            for i, sample in enumerate(samples):
                amplitude_pct = (abs(sample) / 32768) * 100  # Convert to percentage of max amplitude
                binary = int_to_binary_str(sample)
                print(f"{i:5d}  |  {sample:6d}     |  {amplitude_pct:6.2f}%      |  {binary}")
            
            # Print statistics
            print("\nStatistics:")
            print(f"Average amplitude: {sum(abs(s) for s in samples) / len(samples):.2f}")
            print(f"Max amplitude: {max(abs(s) for s in samples)}")
            print(f"Min amplitude: {min(abs(s) for s in samples)}")
            
            return samples
            
    except Exception as e:
        print(f"Error analyzing file: {e}")
        return None

# Main test sequence
try:
    # Initialize hardware
    sd = init_sd()
    mic = init_mic()
    speaker = init_speaker()
    
    print("\nStarting comparison test sequence...")
    
    # Test all combinations
    print("\n1. Recording WITH correction, WITH gain...")
    if record_to_file('mic_test_both.raw', duration_seconds=3, 
                      apply_gain=True, gain=5, apply_correction=True):
        
        print("\n2. Recording WITH correction, NO gain...")
        if record_to_file('mic_test_corr_only.raw', duration_seconds=3, 
                         apply_gain=False, gain=5, apply_correction=True):
            
            print("\n3. Recording NO correction, WITH gain...")
            if record_to_file('mic_test_gain_only.raw', duration_seconds=3, 
                            apply_gain=True, gain=5, apply_correction=False):
                
                print("\n4. Recording NO correction, NO gain...")
                if record_to_file('mic_test_neither.raw', duration_seconds=3, 
                                apply_gain=False, gain=5, apply_correction=False):
                    
                    # Analyze all recordings
                    print("\n=== SAMPLE ANALYSIS ===")
                    samples_both = analyze_samples('mic_test_both.raw')
                    samples_corr = analyze_samples('mic_test_corr_only.raw')
                    samples_gain = analyze_samples('mic_test_gain_only.raw')
                    samples_neither = analyze_samples('mic_test_neither.raw')
                    
                    # Play back all versions
                    print("\n=== PLAYBACK ===")
                    print("\nPlaying: Correction ON, Gain ON...")
                    play_from_file('mic_test_both.raw')
                    time.sleep(1)
                    
                    print("\nPlaying: Correction ON, Gain OFF...")
                    play_from_file('mic_test_corr_only.raw')
                    time.sleep(1)
                    
                    print("\nPlaying: Correction OFF, Gain ON...")
                    play_from_file('mic_test_gain_only.raw')
                    time.sleep(1)
                    
                    print("\nPlaying: Correction OFF, Gain OFF...")
                    play_from_file('mic_test_neither.raw')
    
    print("\nComparison test sequence complete!")

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