import os
import pyttsx3
from gtts import gTTS
from flask import current_app

def generate_audio_pyttsx3(text, filename="article.mp3"):
    """Offline TTS using system voices"""
    engine = pyttsx3.init()
    engine.setProperty('rate', 175)
    engine.setProperty('volume', 0.9)
    engine.save_to_file(text, filename)
    engine.runAndWait()
    return filename

def generate_audio_gtts(text, filename="article.mp3", lang="en"):
    """Online TTS using Google (more natural)"""
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(filename)
    return filename