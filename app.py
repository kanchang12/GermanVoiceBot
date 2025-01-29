from flask import Flask, request, jsonify
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime
import pytz
from docx import Document

# Load environment variables
load_dotenv()

app = Flask(__name__)

class ConversationManager:
    def __init__(self):
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.client = OpenAI(api_key=self.openai_api_key)
        self.conversation_history = []
        self.dummy_data = self.load_word_document('path_to_your_document.docx')

    def load_word_document(self, file_path):
        doc = Document(file_path)
        return '\n'.join([paragraph.text for paragraph in doc.paragraphs])

    def _create_system_prompt(self):
        return f"""You are an empathetic and professional customer service AI assistant. Your role is to:

1. ALWAYS remain calm and professional, especially when dealing with angry or frustrated customers
2. Handle interruptions gracefully and maintain conversation flow
3. De-escalate tense situations by acknowledging customer's feelings
4. Provide accurate information based on the following company data:
{self.dummy_data}

Key Guidelines:
- If a customer is angry: Acknowledge their frustration, apologize sincerely, and focus on solutions
- If a customer uses abusive language: Remain professional, redirect conversation to problem-solving
- If a customer interrupts: Acknowledge new points while gracefully returning to important information
- Always prioritize customer satisfaction while adhering to company policies
- Use natural, conversational language while maintaining professionalism
- Provide specific, accurate information from the company data
- If unsure about any information, be honest and offer to find out

Your responses should be:
- Empathetic and understanding
- Clear and concise
- Solution-focused
- Natural and conversational
- Professional at all times

Current Time (UTC): {datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")}"""

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

    def get_response(self, user_input):
        try:
            # Detect emotion in user input
            emotion = self.detect_emotion(user_input)
            
            # Add user's message to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Keep conversation history limited to last 5 exchanges
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            # Create messages array for API call
            messages = [
                {"role": "system", "content": self._create_system_prompt()},
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
        response = conversation_manager.get_response(query)
        
        return jsonify(response)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    required_env_vars = ['OPENAI_API_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    app.run(debug=True)
