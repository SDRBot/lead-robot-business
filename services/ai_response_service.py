# services/ai_response_service.py
from openai import OpenAI
import json

class AIResponseService:
    """Handles AI-powered email generation and response scoring"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    async def generate_initial_outreach(self, lead_data: Dict, customer_settings: Dict) -> str:
        """Generate personalized initial outreach email"""
        
        prompt = f"""
        You are {customer_settings['ai_name']}, a {customer_settings['ai_role']} at {customer_settings['company_name']}.
        
        Write a personalized cold outreach email to:
        - Name: {lead_data.get('name', 'there')}
        - Company: {lead_data.get('company', 'their company')}
        - Industry: {lead_data.get('industry', 'their industry')}
        
        Company context: {customer_settings['company_description']}
        Value proposition: {customer_settings['value_proposition']}
        Tone: {customer_settings.get('tone', 'professional and friendly')}
        
        Keep it under 150 words, personalized, and include a clear but soft call-to-action.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    async def generate_response(self, conversation_history: List[Dict], customer_settings: Dict) -> Dict:
        """Generate AI response to incoming email"""
        
        conversation_text = "\n".join([
            f"{'Them' if msg['from_lead'] else 'You'}: {msg['content']}"
            for msg in conversation_history
        ])
        
        prompt = f"""
        You are {customer_settings['ai_name']}, responding to this email conversation:
        
        {conversation_text}
        
        Company context: {customer_settings['company_description']}
        Response guidelines: {customer_settings.get('response_guidelines', '')}
        Tone: {customer_settings.get('tone', 'professional and helpful')}
        
        Provide:
        1. A suggested response (keep under 100 words)
        2. Lead interest score (0-100)
        3. Recommended next action
        4. Key conversation insights
        
        Format as JSON.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
    
    async def score_lead_interest(self, email_content: str) -> int:
        """Score lead interest level from their email"""
        
        prompt = f"""
        Score this email response for sales interest level (0-100):
        
        Email: "{email_content}"
        
        Scoring criteria:
        - 90-100: Ready to buy/book demo
        - 70-89: High interest, asking questions
        - 50-69: Moderate interest, engaged
        - 30-49: Low interest, polite response
        - 0-29: Not interested/negative
        
        Return only the number.
        """
        
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        try:
            return int(response.choices[0].message.content.strip())
        except:
            return 50  # Default moderate score
