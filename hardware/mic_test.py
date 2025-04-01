import machine
from machine import I2S, Pin
import time
import os
import uos
import math

print("=== INMP441 I2S MEMS Microphone Test Script ===")
# exec(open('mic_test.py').read())
# exec(open('main.py').read())

# Configuration
SAMPLE_RATE = 40000  # Hz
SAMPLE_BITS = 32    # bits
MIC_SENSITIVITY = -26  # dBFS value expected at MIC_REF_DB
MIC_REF_DB = 94.0     # Value at which point sensitivity is specified
MIC_OFFSET_DB = 3.0103  # Default offset (sine-wave RMS vs. dBFS)
MIC_BITS = 32         # valid number of bits in I2S data
MIC_OVERLOAD_DB = 116.0  # dB - Acoustic overload point
MIC_NOISE_DB = 29     # dB - Noise floor

# Calculate reference amplitude value
MIC_REF_AMPL = math.pow(10, MIC_SENSITIVITY/20) * ((1<<(MIC_BITS-1))-1)

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

# Initialize INMP441 I2S MEMS microphone
def init_mic():
    print("Initializing INMP441 I2S MEMS microphone...")
    
    # Deinitialize any existing I2S instance
    try:
        mic = I2S(0)
        mic.deinit()
        time.sleep(0.1)
    except:
        pass
    
    # Pin Configuration for INMP441:
    # - L/R or SEL: Connect to GND for Left channel (L/R pin on INMP441)
    # - SCK: I2S Serial Clock (SCK pin on INMP441)
    # - WS: I2S Word Select/Clock (WS pin on INMP441)
    # - SD: I2S Serial Data (SD pin on INMP441)
    # - VDD: 3.3V
    # - GND: GND
    
    return I2S(
        0,                  # I2S ID (0 or 1)
        sck=Pin(3),         # BCLK - Bit Clock (SCK on the INMP441)
        ws=Pin(1),          # LRCLK - Word Select (WS on the INMP441)
        sd=Pin(2),          # DOUT - Serial Data (SD on the INMP441)
        mode=I2S.RX,        # Receive mode for microphone
        bits=SAMPLE_BITS,   # 32-bit samples
        format=I2S.STEREO,  # Changed to STEREO to match I2S_CHANNEL_FMT_RIGHT_LEFT
        rate=SAMPLE_RATE,   # 40kHz sample rate
        ibuf=4096          # Increased buffer size (4 * 1024 to match dma_buf_count * dma_buf_len)
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

def apply_noise_filter(samples, threshold=100):
    """Apply a simple noise filter to remove low-amplitude noise"""
    filtered = []
    for sample in samples:
        if abs(sample) > threshold:
            filtered.append(sample)
        else:
            filtered.append(0)
    return filtered

def calculate_dB(samples):
    """Calculate dB value from samples"""
    # Calculate RMS
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    
    # Calculate dB relative to reference
    if rms > 0:
        db = MIC_OFFSET_DB + MIC_REF_DB + 20 * math.log10(rms / MIC_REF_AMPL)
    else:
        db = -float('inf')
    
    return db

def analyze_raw_samples(buffer, num_samples=10):
    """Analyze raw samples from the buffer before any processing"""
    print("\nRaw Sample Analysis:")
    print("Index  |  Raw Value  |  Binary")
    print("-" * 40)
    
    for i in range(0, min(len(buffer), num_samples * 4), 4):
        # Extract the 24-bit value from 32-bit sample
        value = (buffer[i+3] << 24) | (buffer[i+2] << 16) | (buffer[i+1] << 8) | buffer[i]
        # Right shift to get the proper alignment
        sample = value >> 16
        
        # Convert to signed 16-bit
        if sample & 0x8000:
            sample -= 0x10000
            
        # Print binary representation
        binary = bin(sample & 0xFFFF)[2:].zfill(16)
        print(f"{i//4:5d}  |  {sample:6d}     |  {binary}")

def visualize_signal(samples, width=40):
    """Create a simple ASCII visualization of the signal"""
    if not samples:
        return
        
    # Normalize samples to fit in the visualization width
    max_val = max(abs(s) for s in samples)
    if max_val == 0:
        return
        
    print("\nSignal Visualization:")
    print("-" * width)
    for sample in samples:
        # Convert sample to position in visualization
        pos = int((sample / max_val) * (width/2))
        # Create visualization line
        line = " " * (width//2 + pos) + "*"
        print(line)
    print("-" * width)

def analyze_noise_characteristics(samples):
    """Analyze noise characteristics of the samples"""
    if not samples:
        return
        
    # Calculate basic statistics
    abs_samples = [abs(s) for s in samples]
    mean = sum(abs_samples) / len(abs_samples)
    rms = math.sqrt(sum(s * s for s in samples) / len(samples))
    
    # Count samples above different thresholds
    thresholds = [100, 200, 500, 1000, 2000]
    print("\nNoise Analysis:")
    print("Threshold | Samples Above | Percentage")
    print("-" * 40)
    for threshold in thresholds:
        count = sum(1 for s in abs_samples if s > threshold)
        percentage = (count / len(samples)) * 100
        print(f"{threshold:9d} | {count:13d} | {percentage:9.2f}%")
    
    print(f"\nMean amplitude: {mean:.2f}")
    print(f"RMS value: {rms:.2f}")
    
    # Calculate signal-to-noise ratio (SNR)
    if mean > 0:
        snr = 20 * math.log10(rms / mean)
        print(f"Signal-to-Noise Ratio: {snr:.2f} dB")

def record_to_file(filename, duration_seconds=3, apply_gain=False, gain=2, noise_filter=True):
    print(f"Recording for {duration_seconds} seconds directly to {filename}")
    print(f"Settings: gain={'ON' if apply_gain else 'OFF'} ({gain}x), noise filter: {'ON' if noise_filter else 'OFF'}")
    
    # Calculate number of samples
    total_samples = SAMPLE_RATE * duration_seconds
    samples_recorded = 0
    
    # Buffer for DC offset calculation
    dc_buffer = []
    dc_samples = 1000  # Number of samples to use for DC offset calculation
    
    # Buffer for noise analysis
    noise_analysis_buffer = []
    
    try:
        with open(f'/sd/{filename}', 'wb') as f:
            # Record in chunks
            while samples_recorded < total_samples * 2:  # *2 because each output sample is 2 bytes
                buffer = bytearray(4096)  # For 32-bit samples (1024 samples)
                # Read audio samples from the microphone
                mic.readinto(buffer)
                
                # Analyze raw samples for the first chunk
                if samples_recorded == 0:
                    analyze_raw_samples(buffer)
                
                # Process samples - convert from 32-bit to 16-bit
                amplified = bytearray(len(buffer) // 2)  # Output buffer for 16-bit samples
                
                # Process samples in this chunk
                chunk_samples = []
                for i in range(0, len(buffer), 8):  # Changed to 8 bytes (32-bit * 2 channels)
                    # Extract the 32-bit value from buffer
                    value = (buffer[i+3] << 24) | (buffer[i+2] << 16) | (buffer[i+1] << 8) | buffer[i]
                    
                    # Convert to signed 32-bit
                    if value & 0x80000000:
                        value -= 0x100000000
                    
                    # Store sample for DC offset calculation
                    if len(dc_buffer) < dc_samples:
                        dc_buffer.append(value)
                    
                    # Store sample for noise analysis
                    if len(noise_analysis_buffer) < 1000:  # Store up to 1000 samples for analysis
                        noise_analysis_buffer.append(value)
                    
                    # Apply gain if enabled
                    if apply_gain:
                        value = int(value * gain)
                    
                    # Clamp to 16-bit range
                    value = max(min(value, 32767), -32768)
                    
                    chunk_samples.append(value)
                
                # Calculate DC offset from buffer
                if len(dc_buffer) >= dc_samples:
                    dc_offset = sum(dc_buffer) / len(dc_buffer)
                    # Apply DC offset correction to chunk samples
                    chunk_samples = [int(s - dc_offset) for s in chunk_samples]
                
                # Apply noise filter if enabled
                if noise_filter:
                    chunk_samples = apply_noise_filter(chunk_samples)
                
                # Calculate dB value for this chunk
                db = calculate_dB(chunk_samples)
                print(f"Current dB: {db:.1f}")
                
                # Visualize signal for the first chunk
                if samples_recorded == 0:
                    visualize_signal(chunk_samples[:50])  # Show first 50 samples
                
                # Convert samples to bytes and write to file
                for i, sample in enumerate(chunk_samples):
                    out_idx = i * 2
                    amplified[out_idx] = sample & 0xFF
                    amplified[out_idx + 1] = (sample >> 8) & 0xFF
                
                # Write processed data
                f.write(amplified[:len(chunk_samples) * 2])
                samples_recorded += len(chunk_samples)
                
                # Print progress
                progress = (samples_recorded / total_samples) * 100
                print(f"Recording progress: {progress:.1f}%")
        
        # Analyze noise characteristics after recording
        if noise_analysis_buffer:
            analyze_noise_characteristics(noise_analysis_buffer)
        
        print("Recording complete!")
        return True
        
    except Exception as e:
        print("Error during recording:", e)
        import sys
        sys.print_exception(e)  # Print full traceback
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

def compute_rms(samples):
    """Calculate RMS value from a list of samples"""
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))

# Main test sequence
try:
    # Initialize hardware
    sd = init_sd()
    mic = init_mic()
    speaker = init_speaker()
    
    print("\nStarting INMP441 microphone test sequence...")
    
    # Test with different gain levels
    gain_levels = [2, 5, 10]
    for gain in gain_levels:
        print(f"\nRecording with {gain}x gain and noise filter...")
        filename = f'mic_test_{gain}x.raw'
        if record_to_file(filename, duration_seconds=3, 
                         apply_gain=True, gain=gain, noise_filter=True):
            
            # Analyze recording
            print(f"\n=== SAMPLE ANALYSIS for {gain}x gain ===")
            samples = analyze_samples(filename)
            
            if samples:
                # Calculate RMS value
                rms = compute_rms(samples)
                print(f"\n=== RMS VALUE ===")
                print(f"RMS: {rms:.2f}")
            
            # Play back recording
            print(f"\n=== PLAYBACK for {gain}x gain ===")
            print("Playing recording...")
            play_from_file(filename)
            time.sleep(1)  # Wait between playbacks
    
    print("\nINMP441 microphone test sequence complete!")
    print("\nThe recordings have been saved with different gain levels.")
    print("Check the noise analysis output to determine the best gain setting.")
    print("If the recordings are too noisy, try:")
    print("1. Increasing the noise filter threshold")
    print("2. Using a lower gain value")
    print("3. Checking the physical connections")
    print("4. Ensuring the microphone is properly powered")

except Exception as e:
    print("Error in test sequence:", e)
    import sys
    sys.print_exception(e)  # Print full traceback

finally:
    # Clean up
    try:
        mic.deinit()
    except:
        pass
    
    try:
        speaker.deinit()
    except:
        pass
    
    try:
        uos.umount('/sd')
    except:
        pass
    
    print("Test cleanup complete.") 