import requests
import os
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

class OpenRouterClient:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.model = os.getenv('OPENROUTER_MODEL', 'mistralai/mistral-7b-instruct:free')
        self.base_url = "https://openrouter.ai/api/v1"
        
    def generate_description(self, image_context: str) -> Dict[str, str]:
        """Generate image description and hashtags using OpenRouter"""
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        
        prompt = f"""You are a museum curator and historian writing an educational Facebook post about a historical image.

You will receive the FULL metadata of a historical image (title, creator, date, description, subject tags, etc.).
Read ALL details carefully and write an engaging, informative post that helps people learn about this image.

IMAGE METADATA:
{image_context}

Write a Facebook post following this EXACT structure:

TITLE: [A captivating, short title - max 80 characters - that hooks readers]

DESCRIPTION: [Write 4-6 well-organized sentences in this order:
1. Open with what the image shows (subject, scene)
2. Mention the creator/artist and the date/era it's from
3. Explain the historical context or significance
4. Include an interesting fact or detail from the metadata
5. End with why it matters today
Use storytelling tone, not dry facts. Make it educational but engaging.]

HASHTAGS: [8-12 relevant hashtags, comma-separated. Mix general (#history #vintage) with specific ones based on the subject tags, era, location, or creator. Example: #VictorianEra, #1890s, #BlackAndWhitePhotography]

Be accurate - only use facts from the metadata. If metadata is sparse, focus on what IS provided. Never invent dates, names, or facts."""
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': 'You are a helpful social media content creator.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 800,
                    'temperature': 0.7
                },
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Parse the response
            parsed = self._parse_response(content)
            return parsed
            
        except Exception as e:
            print(f"Error generating description: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"OpenRouter response: {e.response.text}")
            return {
                'description': 'Beautiful image from public domain archives.',
                'hashtags': '#publicdomain #art #history #culture',
                'title': 'Historical Image'
            }
    
    def _parse_response(self, content: str) -> Dict[str, str]:
        """Parse the AI response"""
        result = {
            'description': '',
            'hashtags': '',
            'title': ''
        }
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('DESCRIPTION:'):
                result['description'] = line.replace('DESCRIPTION:', '').strip()
            elif line.startswith('HASHTAGS:'):
                result['hashtags'] = line.replace('HASHTAGS:', '').strip()
            elif line.startswith('TITLE:'):
                result['title'] = line.replace('TITLE:', '').strip()
        
        # Fallback if parsing failed
        if not result['description']:
            result['description'] = content
        
        return result
