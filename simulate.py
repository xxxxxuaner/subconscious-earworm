import sounddevice as sd
import soundfile as sf
import numpy as np
import time

# Function to measure ambient noise level
def get_noise_level(duration=1):
    recording = sd.rec(int(duration * 44100), samplerate=44100, channels=1, dtype="float32")
    sd.wait()
    return np.mean(np.abs(recording))

# Function to play an existing song
def play_song(file_path, volume=0.5):
    data, samplerate = sf.read(file_path)
    sd.play(data * volume, samplerate)

# Main loop
is_playing = False
while True:
    noise_level = get_noise_level()
    print(f"🔊 Noise Level: {noise_level:.2f}")
    
    if noise_level > 0.01 and not is_playing:  # Start playing if noise level is high and not already playing
        play_song('test.mp3')  # Replace with the path to your audio file
        is_playing = True
    elif noise_level <= 0.01 and is_playing:  # Stop playing if noise level drops
        sd.stop()
        is_playing = False
    
    time.sleep(5)