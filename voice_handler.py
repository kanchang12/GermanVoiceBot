from gtts import gTTS
import speech_recognition as sr
import io

class VoiceHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def speech_to_text(self, audio_file):
        """Convert speech to text"""
        try:
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                return text
        except Exception as e:
            print(f"Speech-to-text error: {e}")
            return None

    def text_to_speech(self, text):
        """Convert text to speech"""
        try:
            tts = gTTS(text=text, lang='en')
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer
        except Exception as e:
            print(f"Text-to-speech error: {e}")
            return None
