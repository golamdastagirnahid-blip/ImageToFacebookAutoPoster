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
        
        prompt = f"""You are a social media content creator. Based on the following image information, create:
1. An engaging description (2-3 sentences)
2. 5-10 relevant hashtags
3. A short title

Image Context: {image_context}

Format your response as:
DESCRIPTION: [your description]
HASHTAGS: [comma separated hashtags]
TITLE: [short title]"""
        
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
                    'max_tokens': 500
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
