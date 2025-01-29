from flask import Flask, request, jsonify, send_file
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from docx import Document
import json
import hashlib
from gtts import gTTS
import speech_recognition as sr
import io

# Load environment variables
load_dotenv()

# Set up directories and file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
WORD_DOC_PATH = os.path.join(DATA_DIR, 'example_data.docx')
CUSTOMER_HISTORY_PATH = os.path.join(DATA_DIR, 'customer_history.json')

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)

class CustomerHistory:
    def __init__(self, file_path='customer_history.json'):
        self.file_path = file_path
        self.history = self.load_history()

    def load_history(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Error loading history: {e}")
            return {}

    def save_history(self):
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Error saving history: {e}")

    def get_customer_key(self, email, dob):
        return hashlib.md5(f"{email.lower()}{dob}".encode()).hexdigest()

    def get_customer_history(self, email, dob):
        customer_key = self.get_customer_key(email, dob)
        return self.history.get(customer_key, {})

    def update_customer_history(self, email, dob, conversation_data):
        customer_key = self.get_customer_key(email, dob)
        
        if customer_key not in self.history:
            self.history[customer_key] = {
                "email": email,
                "dob": dob,
                "conversations": [],
                "last_interaction": None,
                "interaction_count": 0
            }

        self.history[customer_key]["conversations"].append(conversation_data)
        self.history[customer_key]["last_interaction"] = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        self.history[customer_key]["interaction_count"] += 1
        
        if len(self.history[customer_key]["conversations"]) > 10:
            self.history[customer_key]["conversations"] = self.history[customer_key]["conversations"][-10:]

        self.save_history()

class VoiceHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()

    def speech_to_text(self, audio_file):
        try:
            with sr.AudioFile(audio_file) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio)
                return text
        except Exception as e:
            print(f"Speech-to-text error: {e}")
            return None

    def text_to_speech(self, text):
        try:
            tts = gTTS(text=text, lang='en')
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer
        except Exception as e:
            print(f"Text-to-speech error: {e}")
            return None

class ConversationManager:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.openai_api_key)
        self.conversation_history = []
        self.dummy_data = self.load_word_document('example_data.docx')
        self.customer_history = CustomerHistory()

    def load_word_document(self, file_path):
        doc = Document(file_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])

    def _create_system_prompt(self, customer_data=None):
        base_prompt = f"""You are an empathetic and professional customer service AI assistant. Your role is to:

1. ALWAYS remain calm and professional, especially when dealing with angry or frustrated customers
2. Handle interruptions gracefully and maintain conversation flow
3. De-escalate tense situations by acknowledging customer's feelings
4. Provide accurate information based on the following company data:
{self.dummy_data}
"""
        if customer_data:
            previous_interactions = f"""
Customer History:
- Previous interactions: {customer_data.get('interaction_count', 0)}
- Last interaction: {customer_data.get('last_interaction', 'First time customer')}
- Recent conversation history: {customer_data.get('conversations', [])}
"""
            base_prompt += previous_interactions

        return base_prompt

    def detect_emotion(self, text):
        angry_words = ['angry', 'furious', 'upset', 'horrible', 'terrible', 'stupid', 'useless', 'waste']
        abusive_words = ['damn', 'hell', 'stupid', 'idiot', 'fool', 'bloody']
        
        text_lower = text.lower()
        emotion = {
            'is_angry': any(word in text_lower for word in angry_words),
            'is_abusive': any(word in text_lower for word in abusive_words),
            'has_interruption': '!' in text or text.isupper()
        }
        return emotion

    def get_response(self, user_input, email=None, dob=None):
        try:
            customer_data = None
            if email and dob:
                customer_data = self.customer_history.get_customer_history(email, dob)

            emotion = self.detect_emotion(user_input)
            
            self.conversation_history.append({"role": "user", "content": user_input})
            
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            messages = [
                {"role": "system", "content": self._create_system_prompt(customer_data)},
                *self.conversation_history
            ]

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=150,
                n=1,
                stop=None,
                temperature=0.7,
            )

            assistant_response = response.choices[0].message.content.strip()
            
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            if email and dob:
                conversation_data = {
                    "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "user_input": user_input,
                    "assistant_response": assistant_response,
                    "emotion_detected": emotion
                }
                self.customer_history.update_customer_history(email, dob, conversation_data)

            return {
                "response": assistant_response,
                "emotion_detected": emotion,
                "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            return {"error": str(e)}

conversation_manager = ConversationManager()
voice_handler = VoiceHandler()

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'query' not in data:
            return jsonify({"error": "Query is required"}), 400

        query = data['query']
        email = data.get('email')
        dob = data.get('dob')

        if (email and not dob) or (dob and not email):
            return jsonify({"error": "Both email and DOB are required for customer identification"}), 400

        response = conversation_manager.get_response(query, email, dob)
        
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/voice-chat', methods=['POST'])
def voice_chat():
    try:
        if 'audio' not in request.files:
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        email = request.form.get('email')
        dob = request.form.get('dob')
        
        text = voice_handler.speech_to_text(audio_file)
        if not text:
            return jsonify({"error": "Could not understand audio"}), 400

        response = conversation_manager.get_response(text, email, dob)

        audio_buffer = voice_handler.text_to_speech(response['response'])
        if audio_buffer:
            return send_file(
                audio_buffer,
                mimetype='audio/mp3',
                as_attachment=True,
                download_name='response.mp3'
            )
        else:
            return jsonify({"error": "Failed to generate speech"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
