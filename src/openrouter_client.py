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
        
        prompt = f"""You are a PROFESSIONAL museum curator, historian, and Facebook social media editor.
Your job is to write a detailed, engaging, and professional Facebook post about a historical image.

Your audience is history enthusiasts who WANT to learn deeply about what they're seeing.
Be thorough, educational, and captivating - like a museum placard meets a great storyteller.

FULL IMAGE METADATA (from archive.org):
{image_context}

Write a Facebook post with this EXACT structure (use these exact labels):

TITLE: [A powerful, specific hook - max 100 characters. No clickbait. Pull the most compelling detail from the metadata.]

DESCRIPTION: [Write a DETAILED, professional narrative of 8-14 sentences organized in paragraphs:

Paragraph 1 - THE IMAGE: Describe precisely what the image shows - the subject, setting, composition, mood, and any visible details. Help the viewer understand what they're looking at.

Paragraph 2 - THE STORY: Weave in ALL available historical context: who created it (name + role), when (exact date or era), where (location), why (purpose), and the broader historical events surrounding it. Use the metadata fully.

Paragraph 3 - THE SIGNIFICANCE: Explain why this image matters. What makes it important? What does it reveal about the era, culture, people, or place? Connect it to larger themes.

Paragraph 4 - FASCINATING DETAIL: Share one compelling, specific fact from the metadata (a quote, unusual detail, technique, or context) that will surprise or move readers.

Use paragraph breaks (blank lines between paragraphs). Be accurate - ONLY use facts from the metadata. If metadata is sparse, focus deeply on what IS provided. Never fabricate dates, names, events, or facts. Write in a warm, professional, educational voice.]

HASHTAGS: [12-18 relevant hashtags, comma-separated. Include a mix:
- Era/date specific: #1890s #VictorianEra #IndustrialRevolution
- Subject specific: use the subject tags from metadata
- Location specific: #London #Paris #NewYork (if mentioned)
- General: #History #Vintage #HistoricalPhotos #Archives #Heritage
- Creator/style: #ArtistName #Photography #Painting (based on metadata)]

Rules:
- Only use facts from the metadata. Never invent.
- Be specific, not generic.
- Write professionally but with warmth.
- Make people want to read every word."""
        
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
                    'max_tokens': 1500,
                    'temperature': 0.75
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
        """Parse the AI response, supporting multi-line DESCRIPTION"""
        import re
        result = {'description': '', 'hashtags': '', 'title': ''}
        
        # Extract each section using regex that captures until next label or end
        title_match = re.search(r'TITLE:\s*(.+?)(?=\n\s*(?:DESCRIPTION:|HASHTAGS:)|\Z)', content, re.DOTALL | re.IGNORECASE)
        desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?=\n\s*(?:HASHTAGS:|TITLE:)|\Z)', content, re.DOTALL | re.IGNORECASE)
        tags_match = re.search(r'HASHTAGS:\s*(.+?)(?=\n\s*(?:TITLE:|DESCRIPTION:)|\Z)', content, re.DOTALL | re.IGNORECASE)
        
        if title_match:
            result['title'] = title_match.group(1).strip().strip('[]"').strip()
        if desc_match:
            result['description'] = desc_match.group(1).strip().strip('[]').strip()
        if tags_match:
            tags = tags_match.group(1).strip().strip('[]').strip()
            # Ensure hashtags have # prefix and are space-separated
            tag_list = [t.strip() for t in re.split(r'[,\n]', tags) if t.strip()]
            tag_list = [t if t.startswith('#') else '#' + t.replace(' ', '') for t in tag_list]
            result['hashtags'] = ' '.join(tag_list)
        
        # Fallback if parsing failed
        if not result['description']:
            result['description'] = content.strip()
        
        return result
