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
        self.conversations = {}

    def get_response(self, user_input, call_sid=None):
        try:
            # Initialize new conversation or get existing
            if call_sid not in self.conversations:
                self.conversations[call_sid] = []

            # Clean and prepare user input
            processed_input = user_input.strip()

            # Prevent exact repetition of last response
            if self.conversations[call_sid] and self.conversations[call_sid][-1].get('response') == processed_input:
                return {"response": "I understand. What else would you like to know?"}

            # Build system prompt
            messages = [
                {
                    "role": "system",
                    "content": """You are James, a restaurant voice assistant. Important rules:
                    1. Give short, direct responses under 30 words
                    2. Never suggest calling back or checking websites
                    3. If information isn't in data, give a logical answer based on typical restaurant practices
                    4. Never say you'll check with the team - provide a helpful answer
                    5. Speak naturally like a person
                    6. Don't ask if you can help at the end of responses"""
                }
            ]

            # Add relevant conversation history (last 2 exchanges only)
            recent_history = self.conversations[call_sid][-4:] if self.conversations[call_sid] else []
            messages.extend(recent_history)
            
            # Add current user input
            messages.append({"role": "user", "content": processed_input})

            # Get response from OpenAI with tight constraints
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=messages,
                max_tokens=50,  # Limit token length for faster response
                temperature=0.7,
                presence_penalty=0.6,  # Reduce repetition
                frequency_penalty=0.6   # Reduce repetition
            )

            assistant_response = response.choices[0].message.content.strip()

            # Store conversation
            self.conversations[call_sid].append({"role": "user", "content": processed_input})
            self.conversations[call_sid].append({"role": "assistant", "content": assistant_response})

            return {"response": assistant_response}

        except Exception as e:
            print(f"Error in get_response: {e}")
            return {"response": "I understand. How else can I help you today?"}

# Voice handling routes
@app.route("/incoming-call", methods=['POST'])
def incoming_call():
    response = VoiceResponse()
            # Fixed Gather settings

    gather = Gather(
        input='speech dtmf',
        action='/handle-input',
        method='POST',
        language='en-GB',
        speechTimeout='auto',
        interim=False,
        enhanced=True,
        speechModel='phone_call'
    )
    
    gather.say(
        "Hello, I'm James from The Bavarian Bierhaus. How can I help you today?",
        voice="man",
        language="en-GB"
    )
    
    response.append(gather)
    return str(response)

@app.route("/handle-input", methods=['POST'])
def handle_input():
    response = VoiceResponse()
    user_speech = request.form.get('SpeechResult', '')
    call_sid = request.form.get('CallSid', '')

    if user_speech:
        # Get response from conversation manager
        chat_response = conversation_manager.get_response(user_speech, call_sid)
        
        gather = Gather(
            input='speech dtmf',
            action='/handle-input',
            method='POST',
            language='en-GB',
            speechTimeout='auto',
            enhanced=True,
            speechModel='phone_call'
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
            "I didn't catch that, could you please repeat?",
            voice="man",
            language="en-GB"
        )
        response.append(gather)

    return str(response)

# Initialize conversation manager
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
