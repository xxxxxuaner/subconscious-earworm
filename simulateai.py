import sounddevice as sd
import numpy as np
import time
import requests

# AI music API (replace with actual API)
# AI_MUSIC_API = "https://api.suno.ai/generate"

# Function to measure ambient noise level
def get_noise_level(duration=1):
    recording = sd.rec(int(duration * 44100), samplerate=44100, channels=1, dtype="float32")
    sd.wait()
    return np.mean(np.abs(recording))

# Function to request AI melody
def request_ai_melody():
    print("📡 Requesting AI melody...")
    # response = requests.get(AI_MUSIC_API)  # Replace with real API request
    if response.status_code == 200:
        print("🎶 AI Melody Generated:", response.text)
    else:
        print("❌ API Request Failed")

# Main loop
while True:
    noise_level = get_noise_level()
    print(f"🔊 Noise Level: {noise_level:.2f}")
    
    if noise_level > 0.05:  # Threshold for triggering AI melody
        request_ai_melody()
    
    time.sleep(5)
