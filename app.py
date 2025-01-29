from flask import Flask, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from docx import Document
import json
import hashlib

# Load environment variables
load_dotenv()

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
        # Create a unique key based on email and DOB
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

        # Update customer history
        self.history[customer_key]["conversations"].append(conversation_data)
        self.history[customer_key]["last_interaction"] = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
        self.history[customer_key]["interaction_count"] += 1
        
        # Keep only last 10 conversations
        if len(self.history[customer_key]["conversations"]) > 10:
            self.history[customer_key]["conversations"] = self.history[customer_key]["conversations"][-10:]

        self.save_history()

class ConversationManager:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.openai_api_key)
        self.conversation_history = []
        self.dummy_data = self.load_word_document('path_to_your_document.docx')
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

Please use this history to provide more personalized service while maintaining conversation context.
"""
            base_prompt += previous_interactions

        base_prompt += """
Key Guidelines:
- If a customer is angry: Acknowledge their frustration, apologize sincerely, and focus on solutions
- If a customer uses abusive language: Remain professional, redirect conversation to problem-solving
- If a customer interrupts: Acknowledge new points while gracefully returning to important information
- Always prioritize customer satisfaction while adhering to company policies
- Use natural, conversational language while maintaining professionalism
- Provide specific, accurate information from the company data
- If unsure about any information, be honest and offer to find out

Current Time (UTC): {datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")}"""

        return base_prompt

    def detect_emotion(self, text):
        # Simple emotion detection based on keywords
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
            # Get customer history if email and dob are provided
            customer_data = None
            if email and dob:
                customer_data = self.customer_history.get_customer_history(email, dob)

            # Detect emotion in user input
            emotion = self.detect_emotion(user_input)
            
            # Add user's message to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Keep conversation history limited to last 5 exchanges
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            # Create messages array for API call
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

            # Get the response
            assistant_response = response.choices[0].message.content.strip()
            
            # Add assistant's response to conversation history
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            # Update customer history if email and dob are provided
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

# Initialize Conversation Manager
conversation_manager = ConversationManager()

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'query' not in data:
            return jsonify({"error": "Query is required"}), 400

        query = data['query']
        email = data.get('email')
        dob = data.get('dob')

        # Validate email and DOB if provided
        if (email and not dob) or (dob and not email):
            return jsonify({"error": "Both email and DOB are required for customer identification"}), 400

        response = conversation_manager.get_response(query, email, dob)
        
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    required_env_vars = ['OPENAI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    app.run(debug=True)
