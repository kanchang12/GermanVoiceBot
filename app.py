from flask import Flask, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
import json
import hashlib
import asyncio
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)
load_dotenv()

# Initialize empty restaurant data
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

class ConversationManager:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.conversation_memory = {}
        self.memory_timeout = 300  # 5 minutes
        self.response_cache = {}
        self.current_time = datetime.now(pytz.UTC)

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
        return emotions

    async def process_speech(self, user_speech):
        """Pre-process speech input"""
        return user_speech.strip()

    async def get_response(self, user_input, phone_number=None, call_sid=None):
        try:
            current_time = datetime.now(pytz.UTC)
            
            # Initialize or get conversation memory
            if call_sid not in self.conversation_memory:
                self.conversation_memory[call_sid] = {
                    'messages': [],
                    'timestamp': current_time,
                    'start_time': current_time
                }
            
            # Process speech
            processed_input = await self.process_speech(user_input)
            
            # Get emotion context
            emotions = self.detect_emotion_and_context(processed_input)
            
            # Calculate time in conversation
            time_diff = (current_time - self.conversation_memory[call_sid]['start_time']).total_seconds()
            
            if time_diff <= self.memory_timeout:
                # Build conversation history
                messages = [
                    {
                        "role": "system",
                        "content": f"""
                        You are James, a knowledgeable restaurant assistant for our establishment.
                        Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC

                        Restaurant Information:
                        {my_sample_data}

                        Key Guidelines:
                        1. Speak naturally and warmly like a real person
                        2. Never direct customers to check websites or other sources
                        3. Only provide information that exists in the restaurant data
                        4. If information isn't in the reference data, politely say you'll check with the team
                        5. Don't repeat phrases unless specifically asked
                        6. Maintain conversation context and reference previous discussion points
                        7. Be direct and helpful - avoid unnecessarily repeating "How may I assist you"
                        8. Use the full conversation history to provide context-aware responses
                        """
                    }
                ]

                # Add ALL previous conversation history
                messages.extend(self.conversation_memory[call_sid]['messages'])
                messages.append({"role": "user", "content": processed_input})

                # Get OpenAI response
                response = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model="gpt-4-turbo-preview",
                    messages=messages,
                    max_tokens=150,
                    temperature=0.7
                )

                assistant_response = response.choices[0].message.content.strip()

                # Update conversation memory with new messages
                self.conversation_memory[call_sid]['messages'].extend([
                    {"role": "user", "content": processed_input},
                    {"role": "assistant", "content": assistant_response}
                ])

                return {
                    "response": assistant_response,
                    "emotions_detected": emotions,
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "conversation_duration": time_diff
                }
            else:
                # Reset conversation after timeout
                self.conversation_memory[call_sid] = {
                    'messages': [],
                    'timestamp': current_time,
                    'start_time': current_time
                }
                return {
                    "response": "I apologize, but our conversation timeout has been reached. How may I help you with your new request?",
                    "emotions_detected": emotions,
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "conversation_duration": time_diff
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
        enhanced=True,
        speechModel='phone_call',
        interim=True
    )
    
    gather.say(
        "Hello! I'm James from the restaurant. How can I help you today?",
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
            speechTimeout='1s',
            enhanced=True,
            interim=True,
            speechModel='phone_call',
            languages=['en-US', 'en-GB', 'en-AU', 'en-IN'],
            profanityFilter=False
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
            "I didn't catch that. Could you please repeat?",
            voice="man",
            language="en-GB"
        )
        
        response.append(gather)

    return str(response)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
