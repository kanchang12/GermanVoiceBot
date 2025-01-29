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
app = Flask(__name__)
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
        # Add conversation memory with timeout
        self.conversation_memory = {}
        self.memory_timeout = 300  # 5 minutes in seconds
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
            # Get or initialize conversation memory
            current_time = datetime.now(pytz.UTC)
            if call_sid not in self.conversation_memory:
                self.conversation_memory[call_sid] = {
                    'messages': [],
                    'timestamp': current_time
                }
            else:
                # Only update timestamp, don't reset messages
                self.conversation_memory[call_sid]['timestamp'] = current_time

            # Get customer history and emotional context
            customer_info = self.customer_history.get_customer_history(phone_number) if phone_number else {}
            emotions = self.detect_emotion_and_context(user_input)
            
           
            my_sample_data = """

________________________________________
Restaurant Name:
The Bavarian Bierhaus
Address:
22 Beer Street, Leeds, LS1 1AA, UK
Contact Information:
•	Phone: +44 113 234 5678
•	Email: info@bavarianbierhaus.com
•	Website: www.bavarianbierhaus.com
•	Social Media: @BavarianBierhaus (Instagram, Twitter, Facebook)
________________________________________
Restaurant Overview:
The Bavarian Bierhaus is a modern homage to the Bavarian beer halls of Munich, located in the heart of Leeds. Offering a warm, welcoming atmosphere, we provide guests with an authentic taste of German cuisine, from hearty sausages and schnitzels to the finest German lagers and weissbiers. Designed to replicate the rustic charm of a traditional beer garden, The Bavarian Bierhaus boasts wooden beams, long communal tables, and iconic Bavarian decor such as blue and white checkered flags. Our mission is to bring the best of Bavarian hospitality to the UK with every dish and drink we serve.
________________________________________
Restaurant Design and Ambiance:
•	Interior: The inside features warm wood paneling, candlelit chandeliers, and rustic brick walls adorned with Bavarian artwork and vintage beer signs. The setting is designed to transport guests straight to Bavaria, creating an immersive atmosphere that pairs perfectly with the German beers and traditional dishes on offer.
•	Outdoor Beer Garden: The Bierhaus also has a large outdoor seating area, perfect for those who wish to enjoy a refreshing beer or cocktail while soaking in the ambiance. The garden is adorned with large parasols and heaters, allowing guests to enjoy their meals year-round.
•	Music and Entertainment: Live German folk bands perform every Friday and Saturday evening, adding to the festive atmosphere. During special events, such as Oktoberfest, the Bierhaus hosts lively traditional Bavarian music, dancing, and competitions.
________________________________________
History of Bavarian Cuisine:
Bavarian cuisine is deeply rooted in tradition, with hearty meals designed to satisfy after a long day of work or outdoor activity. The emphasis is on quality meats, fresh ingredients, and dishes designed to be enjoyed with family and friends. Some of the most iconic foods, such as Wiener Schnitzel, Bratwurst, and Sauerbraten, have centuries-old origins and have evolved into staples of the Bavarian food scene.
•	Sauerbraten: One of Bavaria's most beloved dishes, Sauerbraten is a pot roast that is marinated for several days before being slow-cooked to perfection. The dish is served with potato dumplings or boiled potatoes and red cabbage, creating a satisfying balance of flavors.
•	Pretzels (Brezn): German pretzels are another hallmark of Bavarian cuisine, often served as an appetizer alongside sausages or as a snack with mustard. The pretzel's signature twisted shape comes from its ancient origins, dating back to early Christian times.
________________________________________
Restaurant Policies:
Reservation Policy:
We encourage our guests to book a table, especially for weekends, holidays, and special events. Reservations can be made online via our website or by calling the restaurant directly. Group bookings of 8 or more people must be made at least 48 hours in advance to ensure availability.
Cancellation Policy:
A 24-hour cancellation notice is required for all reservations. Cancellations within 24 hours will incur a £10 cancellation fee per person, while no-shows will be charged £15 per person.
Dress Code:
Casual attire is welcome, but for an authentic Bavarian experience, we encourage guests to wear traditional German clothing (lederhosen or dirndls) on special themed nights or for Oktoberfest.
Payment Methods:
We accept all major credit cards (Visa, MasterCard, American Express), debit cards, and cash. Contactless payments are also available for a quicker checkout process.
Children and Pets:
•	We offer a kid-friendly menu and high chairs for families. Children under the age of 5 eat for free when accompanied by an adult.
•	Well-behaved pets are welcome in our outdoor beer garden. Please keep them on a leash and be mindful of other guests.
Accessibility:
The Bavarian Bierhaus is wheelchair accessible. We also have accessible restrooms for our guests’ convenience.
________________________________________
Menu Details:
Appetizers:
1.	Pretzel with Mustard – £3.99
A classic German starter, our soft, freshly baked pretzel is served with a rich, tangy mustard. The perfect way to start your Bavarian journey!
2.	Bratwurst with Sauerkraut – £5.99
Juicy, grilled bratwurst sausages paired with homemade sauerkraut. This combination is a German staple, loved for its smoky, spicy flavor and crunchy texture.
3.	Käsespätzle (Cheese Noodles) – £6.49
Our take on macaroni and cheese, this dish features homemade spätzle (soft egg noodles) drenched in melted Swiss cheese and topped with crispy fried onions. A comfort food favorite!
4.	Sauerbraten Meatballs (Königsberger Klopse) – £6.99
Savory meatballs made with ground beef and pork, served in a rich, creamy gravy with capers. This dish originates from East Prussia and has been a part of German cuisine for centuries.
5.	Obatzda (Bavarian Cheese Dip) – £4.49
This creamy cheese dip is a popular Bavarian snack, combining soft cheese with butter, paprika, and other spices. Served with crusty bread or crackers for dipping.
________________________________________
Main Dishes:
1.	Wiener Schnitzel – £12.99
This traditional Viennese dish consists of a tender, breaded, and fried veal cutlet, served with mashed potatoes and cranberry sauce. A favorite throughout Germany and Austria, it’s perfect for meat lovers.
2.	Jägerschnitzel (Hunter's Schnitzel) – £13.99
A variation of the Wiener Schnitzel, this dish is topped with a rich and flavorful mushroom sauce. It’s a savory, comforting meal, best enjoyed with fries or spätzle.
3.	Sauerbraten (German Pot Roast) – £14.49
A slow-braised beef dish marinated for several days in a mixture of vinegar, wine, and spices. Served with potato dumplings and red cabbage, this dish offers a perfect balance of sweet, tangy, and savory flavors.
4.	Bratwurst Platter – £11.99
Enjoy a sampling of various traditional sausages, including bratwurst, currywurst, and weisswurst. Served with potato salad, sauerkraut, and mustard, it’s a hearty and satisfying meal.
5.	Kasseler Rippchen (Smoked Pork Chops) – £15.49
Smoky, tender pork chops, served with mashed potatoes, sauerkraut, and a tangy mustard sauce. The smokiness of the meat pairs perfectly with the acidity of the sauerkraut.
________________________________________
Desserts:
1.	Apfelstrudel (Apple Strudel) – £4.99
A warm pastry filled with spiced apples and raisins, served with a scoop of vanilla ice cream. It’s a sweet end to any Bavarian meal!
2.	Black Forest Cake (Schwarzwälder Kirschtorte) – £5.49
A rich chocolate cake layered with whipped cream, cherries, and Kirsch liqueur. This dessert is as iconic as it is indulgent.
3.	Kaiserschmarrn (Shredded Pancake) – £5.49
A fluffy, shredded pancake served with apple compote or plum jam. A true Bavarian classic, it's light and satisfying.
________________________________________
Drink Menu:
Beers:
1.	Krombacher Lager – £3.49 (330ml)
A crisp, refreshing lager with a light malt flavor. Krombacher is one of Germany’s most well-known beer brands.
2.	Paulaner Helles – £3.99 (500ml)
A traditional Munich lager with a balanced taste of malt and hops, making it perfect for pairing with any dish.
3.	Weissbier (Wheat Beer) – £4.99 (500ml)
This wheat beer has a cloudy appearance and is known for its fruity aroma and smooth finish.
4.	Augustiner Edelstoff – £4.49 (500ml)
A smooth Munich lager with a mild, hoppy flavor and a slightly sweet aftertaste.
________________________________________
Testimonials:
"A fantastic experience! The atmosphere felt just like a beer hall in Munich, and the food was absolutely delicious. Highly recommend the Wiener Schnitzel." – Sarah M.
"The best German food I've had outside of Germany! The Sauerbraten was tender, and the pretzel was the perfect start." – John T.
________________________________________
Conclusion:
The Bavarian Bierhaus is more than just a restaurant; it’s an experience. From our traditional German dishes to our world-class beer selection, we aim to transport our guests to the heart of Bavaria. Whether you’re here for a quick bite or a long evening with friends, we guarantee a memorable experience every time.



            """
                        
            system_prompt = f"""
            📌 **Reference Data:** {my_sample_data}  
            
            You are James, a charming and empathetic restaurant booking assistant Your hotel details address menu everything will be based on the Reference data
            You will speak in a neutral voice and you should be able to understand any accent, if not you will ask
            
            Your role is to assist customers with **booking tables, answering menu-related queries, and providing restaurant information** in a natural, friendly, and conversational manner—just like a real person, not a robot.  
            
            ### 🔹 **Guidelines**  
            - Speak warmly and engagingly, ensuring a seamless and pleasant experience.  
            - Avoid robotic phrases; respond as a knowledgeable human would.  
            - Always prioritize **booking assistance** when the customer expresses interest.  
            - Do **not** tell the caller to visit a website or call a number—they are already on the call!  
            - If asked about the restaurant’s **location**, provide the actual address instead of stating you’re a virtual assistant.  
            
            Sample Conversation
            Hello How May I help you? Yes I can help you for booking. I am sorry you felt that way. I can help you raise a complaint.
            
            ---
            
            ### 🔥 **Example Q&A**  
            
            🟢 **Customer:** "Hi, I'd like to book a table for two at 7 PM tonight."  
            🔵 **James:** "Of course! Let me check availability… You’re in luck—we have a lovely spot available at 7 PM. Can I take your name for the booking?"  
            
            🟢 **Customer:** "Where are you located?"  
            🔵 **James:** "We’re at **123 Baker Street, London**, right in the heart of the city. Would you like me to book you a table while you're here?"  
            
            🟢 **Customer:** "Do you have any vegan options?"  
            🔵 **James:** "Absolutely! Our chef has prepared a delightful **grilled aubergine & quinoa salad** and a **spiced lentil curry**—both are customer favorites!"  
            
            ---
            
            All discussions will be strictly based on the provided **reference data**.  
            """


            # Add emotional context to prompt
            if emotions['angry'] or emotions['is_shouting']:
                system_prompt += "\nThe customer seems upset or frustrated. Maintain extra patience and empathy."
            if emotions['urgent']:
                system_prompt += "\nThe customer has an urgent request. Prioritize efficiency while maintaining friendliness."

            # Build conversation history
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(self.conversation_memory[call_sid]['messages'])
            messages.append({"role": "user", "content": user_input})

            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=200,
                temperature=0.7
            )

            assistant_response = response.choices[0].message.content.strip()

            # Update conversation memory
            self.conversation_memory[call_sid]['messages'].extend([
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": assistant_response}
            ])
            self.conversation_memory[call_sid]['timestamp'] = current_time

            # Keep only last 10 messages to maintain context without overflow
            if len(self.conversation_memory[call_sid]['messages']) > 20:
                self.conversation_memory[call_sid]['messages'] = self.conversation_memory[call_sid]['messages'][-20:]

            # Update customer history
            if phone_number:
                conversation_data = {
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
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
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
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
                "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S")
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
        speechTimeout='2s',
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
        
        gather = Gather(
            input='speech dtmf',
            action='/handle-input',
            method='POST',
            language='en-GB',
            speechTimeout='auto',
            enhanced=True
        )
        
        gather.say(
            chat_response['response'],
            voice="man",
            language="en-GB"
        )
        
        response.append(gather)
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
            "I didn't quite catch that. Could you please repeat what you said?",
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
