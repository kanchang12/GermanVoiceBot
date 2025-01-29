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

# Setup paths and configurations
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CUSTOMER_HISTORY_PATH = os.path.join(DATA_DIR, 'customer_history.json')
CALL_HISTORY_PATH = os.path.join(DATA_DIR, 'call_history.json')
WORD_DOC_PATH = os.path.join(DATA_DIR, 'restaurant_info.docx')
os.makedirs(DATA_DIR, exist_ok=True)

class DocumentReader:
    def __init__(self, doc_path=WORD_DOC_PATH):
        self.doc_path = doc_path
        self.restaurant_info = self.read_document()

    def read_document(self):
        try:
            if not os.path.exists(self.doc_path):
                return {}

            doc = Document(self.doc_path)
            restaurant_info = {
                "menu_items": [],
                "specials": [],
                "facilities": [],
                "policies": [],
                "contact_info": {},
                "raw_content": []
            }

            current_section = "raw_content"
            
            for paragraph in doc.paragraphs:
                text = paragraph.text.strip()
                if not text:
                    continue

                # Store raw content
                restaurant_info["raw_content"].append(text)

                # Basic section detection
                lower_text = text.lower()
                if "menu" in lower_text:
                    current_section = "menu_items"
                elif "special" in lower_text:
                    current_section = "specials"
                elif "facilit" in lower_text or "amenit" in lower_text:
                    current_section = "facilities"
                elif "polic" in lower_text or "rule" in lower_text:
                    current_section = "policies"
                elif "contact" in lower_text or "phone" in lower_text or "email" in lower_text:
                    current_section = "contact_info"
                
                # Store in appropriate section
                if current_section in restaurant_info:
                    if isinstance(restaurant_info[current_section], list):
                        restaurant_info[current_section].append(text)
                    else:
                        # For contact_info, store as key-value pairs
                        if ":" in text:
                            key, value = text.split(":", 1)
                            restaurant_info[current_section][key.strip()] = value.strip()

            return restaurant_info

        except Exception as e:
            print(f"Error reading document: {e}")
            return {}

    def get_info(self, section=None):
        if section:
            return self.restaurant_info.get(section, {})
        return self.restaurant_info

class CallHistory:
    def __init__(self, file_path=CALL_HISTORY_PATH):
        self.file_path = file_path
        self.history = self.load_history()

    def load_history(self):
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            return {
                "calls": [],
                "statistics": {
                    "total_calls": 0,
                    "total_duration": 0,
                    "average_duration": 0,
                    "emotions_detected": {
                        "angry": 0,
                        "frustrated": 0,
                        "positive": 0
                    }
                }
            }
        except Exception as e:
            print(f"Error loading call history: {e}")
            return {"calls": [], "statistics": {}}

    def save_history(self):
        try:
            with open(self.file_path, 'w') as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Error saving call history: {e}")

    def update_call(self, call_data):
        """
        Update call history with new call data
        call_data should include:
        - call_sid
        - phone_number
        - start_time
        - end_time (optional)
        - duration (optional)
        - emotions_detected
        - conversation_summary
        - booking_made (boolean)
        - complaint_filed (boolean)
        """
        # Find existing call or create new entry
        call_entry = next(
            (call for call in self.history["calls"] if call["call_sid"] == call_data["call_sid"]),
            None
        )

        if call_entry:
            # Update existing call
            call_entry.update(call_data)
        else:
            # Add new call
            self.history["calls"].append(call_data)

        # Update statistics
        self._update_statistics()
        self.save_history()

    def _update_statistics(self):
        """Update overall statistics based on call history"""
        stats = {
            "total_calls": len(self.history["calls"]),
            "total_duration": 0,
            "emotions_detected": {
                "angry": 0,
                "frustrated": 0,
                "positive": 0
            },
            "bookings_made": 0,
            "complaints_filed": 0
        }

        for call in self.history["calls"]:
            if "duration" in call:
                stats["total_duration"] += call["duration"]

            if "emotions_detected" in call:
                for emotion, count in call["emotions_detected"].items():
                    if emotion in stats["emotions_detected"]:
                        stats["emotions_detected"][emotion] += count

            if call.get("booking_made", False):
                stats["bookings_made"] += 1
            if call.get("complaint_filed", False):
                stats["complaints_filed"] += 1

        stats["average_duration"] = (
            stats["total_duration"] / stats["total_calls"]
            if stats["total_calls"] > 0 else 0
        )

        self.history["statistics"] = stats

    def get_call_history(self, call_sid=None, phone_number=None):
        """Get call history for specific call or phone number"""
        if call_sid:
            return next(
                (call for call in self.history["calls"] if call["call_sid"] == call_sid),
                None
            )
        elif phone_number:
            return [
                call for call in self.history["calls"]
                if call["phone_number"] == phone_number
            ]
        return self.history

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

    def get_customer_history(self, phone_number):
        customer_key = hashlib.md5(phone_number.encode()).hexdigest()
        return self.history.get(customer_key, {})

    def update_customer_history(self, phone_number, conversation_data):
        customer_key = hashlib.md5(phone_number.encode()).hexdigest()
        
        if customer_key not in self.history:
            self.history[customer_key] = {
                "phone": phone_number,
                "first_interaction": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                "conversations": [],
                "preferences": {
                    "seating_preference": None,
                    "dietary_restrictions": [],
                    "favorite_dishes": [],
                    "special_requests": []
                },
                "bookings": [],
                "complaints": [],
                "satisfaction_score": None,
                "total_visits": 0,
                "total_spent": 0
            }
        
        self.history[customer_key]["conversations"].append(conversation_data)
        self.history[customer_key]["last_interaction"] = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        
        # Update preferences based on conversation
        if "preferences" in conversation_data:
            self.history[customer_key]["preferences"].update(conversation_data["preferences"])
        
        # Update bookings if applicable
        if "booking" in conversation_data:
            self.history[customer_key]["bookings"].append(conversation_data["booking"])
            self.history[customer_key]["total_visits"] += 1
        
        # Update complaints if applicable
        if "complaint" in conversation_data:
            self.history[customer_key]["complaints"].append(conversation_data["complaint"])
        
        self.save_history()

class ConversationManager:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.openai_api_key)
        self.customer_history = CustomerHistory()
        self.call_history = CallHistory()
        self.doc_reader = DocumentReader()
        self.conversation_state = {}
        self.restaurant_info = self.doc_reader.get_info()

    def detect_emotion_and_context(self, text):
        emotion_indicators = {
            'angry': ['angry', 'furious', 'upset', 'horrible', 'terrible', 'stupid', 'useless'],
            'frustrated': ['annoying', 'frustrating', 'difficult', 'problem', 'issue'],
            'urgent': ['immediately', 'urgent', 'asap', 'emergency', 'right now'],
            'positive': ['happy', 'great', 'wonderful', 'excellent', 'perfect', 'thanks'],
            'confused': ['confused', 'unsure', 'don\'t understand', 'what do you mean']
        }
        
        text_lower = text.lower()
        emotions = {
            emotion: any(word in text_lower for word in words)
            for emotion, words in emotion_indicators.items()
        }
        
        emotions['is_shouting'] = text.isupper() or text.count('!') > 1
        emotions['has_interruption'] = '...' in text or '?' in text
        
        return emotions

    def get_response(self, user_input, phone_number=None, call_sid=None):
        try:
            # Get customer history and emotional context
            customer_info = self.customer_history.get_customer_history(phone_number) if phone_number else {}
            emotions = self.detect_emotion_and_context(user_input)
            
            # Get restaurant information
            restaurant_info = self.restaurant_info
            
            # Comprehensive system prompt with restaurant information
            system_prompt = f"""You are James, a charming and empathetic restaurant booking assistant with a warm British accent. You're 35 years old and have been in the restaurant industry for 15 years. Your responses should be natural, friendly, and conversational - like a real person, not a robot.

Restaurant Information:
Menu Items: {restaurant_info.get('menu_items', [])}
Daily Specials: {restaurant_info.get('specials', [])}
Facilities: {restaurant_info.get('facilities', [])}
Policies: {restaurant_info.get('policies', [])}
Contact Information: {restaurant_info.get('contact_info', {})}

Key Features to Address:
1. Bookings: Tables (indoor/outdoor), special occasions, group bookings
2. Menu Information: Daily specials, kids menu, vegetarian/vegan options, allergen information
3. Facilities: Parking, accessibility, high chairs, baby changing
4. Special Requirements: Dietary restrictions, wheelchair access, quiet areas
5. Additional Services: Private dining, catering, gift cards

Customer History and Preferences:
{json.dumps(customer_info, indent=2)}

Conversation Style:
- Use natural language and friendly tone
- Acknowledge emotions and respond appropriately
- Handle interruptions gracefully
- Maintain conversation flow
- Use British expressions naturally
- Show personality while remaining professional"""

            # Add emotional context to prompt
            if emotions['angry'] or emotions['is_shouting']:
                system_prompt += "\nThe customer seems upset or frustrated. Maintain extra patience and empathy."
            if emotions['urgent']:
                system_prompt += "\nThe customer has an urgent request. Prioritize efficiency while maintaining friendliness."

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]

            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )

            assistant_response = response.choices[0].message.content.strip()

            # Update customer history
            if phone_number:
                conversation_data = {
                    "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "user_input": user_input,
                    "assistant_response": assistant_response,
                    "emotions_detected": emotions,
                    "call_sid": call_sid
                }
                self.customer_history.update_customer_history(phone_number, conversation_data)

            # Update call history
            if call_sid:
                call_data = {
                    "call_sid": call_sid,
                    "phone_number": phone_number,
                    "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                    "emotions_detected": emotions,
                    "conversation": {
                        "user_input": user_input,
                        "assistant_response": assistant_response
                    }
                }
                self.call_history.update_call(call_data)

            return {
                "response": assistant_response,
                "emotions_detected": emotions,
                "timestamp": datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            print(f"Error in get_response: {e}")
            return {"error": str(e)}

# Initialize manager
conversation_manager = ConversationManager()

@app.route("/incoming-call", methods=['POST'])
def incoming_call():
    response = VoiceResponse()
    gather = Gather(
        input='speech dtmf',
        action='/handle-input',
        method='POST',
        language='en-GB',
        speechTimeout='auto',
        enhanced=True
    )
    
    # Warm, friendly greeting
    gather.say(
        "Hello! I'm James, your restaurant assistant. How may I help you today?",
        voice="man",
        language="en-GB"
    )
    
    response.append(gather)
    return str(response)




@app.route("/handle-input", methods=['POST'])
def handle_input():
    response = VoiceResponse()
    
    phone_number = request.form.get('From', '')
    call_sid = request.form.get('CallSid', '')
    user_speech = request.form.get('SpeechResult', '')

    if user_speech:
        chat_response = conversation_manager.get_response(
            user_speech,
            phone_number=phone_number,
            call_sid=call_sid
        )
        
        # Dynamic response handling
        gather = Gather(
            input='speech dtmf',
            action='/handle-input',
            method='POST',
            language='en-GB',
            speechTimeout='auto',
            enhanced=True
        )
        
        # Natural pauses and emphasis in speech
        gather.say(
            chat_response['response'],
            voice="man",
            language="en-GB"
        )
        
        response.append(gather)
        
        # Friendly fallback
        response.say(
            "I didn't quite catch that. Could you please say that again?",
            voice="man",
            language="en-GB"
        )
    else:
        gather = Gather(
            input='speech dtmf',
            action='/handle-input',
            method='POST',
            language='en-GB',
            speechTimeout='auto',
            enhanced=True
        )
        gather.say(
            "I'm sorry, I didn't catch that. Could you please repeat what you said?",
            voice="man",
            language="en-GB"
        )
        response.append(gather)

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
