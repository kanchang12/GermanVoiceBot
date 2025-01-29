from flask import Flask, request, jsonify
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
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
import io

# Load environment variables
load_dotenv()

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
WORD_DOC_PATH = os.path.join(DATA_DIR, 'example_data.docx')
CUSTOMER_HISTORY_PATH = os.path.join(DATA_DIR, 'customer_history.json')

# Create data directory
os.makedirs(DATA_DIR, exist_ok=True)

# Initialize Flask
app = Flask(__name__)

# Twilio setup
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

class CustomerHistory:
    def __init__(self, file_path=CUSTOMER_HISTORY_PATH):
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

    def get_customer_key(self, phone_number):
        return hashlib.md5(phone_number.encode()).hexdigest()

    def update_customer_history(self, phone_number, conversation_data):
        customer_key = self.get_customer_key(phone_number)
        
        if customer_key not in self.history:
            self.history[customer_key] = {
                "phone": phone_number,
                "conversations": [],
                "last_interaction": None,
                "bookings": [],
                "complaints": []
            }

        self.history[customer_key]["conversations"].append(conversation_data)
        self.history[customer_key]["last_interaction"] = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        self.save_history()

class ConversationManager:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.openai_api_key)
        self.customer_history = CustomerHistory()
        
        # Menu options
        self.menu = {
            "1": "Make a Booking",
            "2": "Check Booking Status",
            "3": "File a Complaint",
            "4": "Speak to an Agent"
        }

    def detect_emotion(self, text):
        angry_words = ['angry', 'furious', 'upset', 'horrible', 'terrible', 'stupid', 'useless']
        abusive_words = ['damn', 'hell', 'stupid', 'idiot', 'fool']
        
        text_lower = text.lower()
        emotion = {
            'is_angry': any(word in text_lower for word in angry_words),
            'is_abusive': any(word in text_lower for word in abusive_words),
            'has_interruption': '!' in text or text.isupper()
        }
        return emotion

    def get_response(self, user_input, phone_number=None, context=None):
        try:
            emotion = self.detect_emotion(user_input)
            
            # Create system prompt based on context and emotion
            system_prompt = "You are a professional customer service AI assistant with a British accent (male, age 35). "
            if emotion['is_angry'] or emotion['is_abusive']:
                system_prompt += "The customer seems upset. Remain calm and professional. "
            if context:
                system_prompt += f"Current context: {context}. "

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )

            assistant_response = response.choices[0].message.content.strip()

            if phone_number:
                conversation_data = {
                    "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "user_input": user_input,
                    "assistant_response": assistant_response,
                    "emotion_detected": emotion,
                    "context": context
                }
                self.customer_history.update_customer_history(phone_number, conversation_data)

            return {
                "response": assistant_response,
                "emotion_detected": emotion,
                "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            return {"error": str(e)}

# Initialize managers
conversation_manager = ConversationManager()

@app.route("/incoming-call", methods=['POST'])
def incoming_call():
    response = VoiceResponse()
    gather = Gather(input='speech dtmf', action='/handle-input', method='POST', language='en-GB')
    gather.say("Welcome to our service. Please select from the following options:", voice="man", language="en-GB")
    
    # Read out menu options
    for key, value in conversation_manager.menu.items():
        gather.say(f"Press {key} for {value}", voice="man", language="en-GB")
    
    response.append(gather)
    return str(response)

@app.route("/handle-input", methods=['POST'])
def handle_input():
    response = VoiceResponse()
    
    # Get caller's phone number
    phone_number = request.form.get('From', '')
    
    # Get user input (speech or dtmf)
    user_speech = request.form.get('SpeechResult')
    user_digits = request.form.get('Digits')

    # Determine context based on input
    context = None
    if user_digits:
        context = conversation_manager.menu.get(user_digits)
    
    # Get response from conversation manager
    if user_speech or user_digits:
        input_text = user_speech if user_speech else f"Menu option {user_digits}"
        chat_response = conversation_manager.get_response(input_text, phone_number, context)
        
        # Handle response
        response.say(chat_response['response'], voice="man", language="en-GB")
        
        # If emotion detected, handle accordingly
        if chat_response['emotion_detected']['is_angry'] or chat_response['emotion_detected']['is_abusive']:
            response.say("I understand you're frustrated. Let me transfer you to a human agent.", 
                        voice="man", language="en-GB")
            response.dial("+1234567890")  # Replace with actual agent number
        else:
            # Continue conversation
            gather = Gather(input='speech', action='/handle-input', method='POST', language='en-GB')
            gather.say("Is there anything else I can help you with?", voice="man", language="en-GB")
            response.append(gather)
    else:
        response.say("I didn't catch that. Could you please repeat?", voice="man", language="en-GB")
        response.redirect('/incoming-call')

    return str(response)

@app.route('/make-call', methods=['POST'])
def make_call():
    try:
        data = request.json
        if not data or 'phone_number' not in data:
            return jsonify({"error": "Phone number is required"}), 400

        call = twilio_client.calls.create(
            to=data['phone_number'],
            from_=TWILIO_PHONE_NUMBER,
            url=request.url_root + 'incoming-call'
        )
        
        return jsonify({
            "status": "success",
            "call_sid": call.sid
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
