import requests
import os
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

class OpenRouterClient:
    def __init__(self):
        # ===== GROQ (Primary - faster, larger free quota) =====
        self.groq_api_key = os.getenv('GROQ_API_KEY', '').strip()
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"
        self.groq_models = [
            'llama-3.3-70b-versatile',      # Best quality - 70B
            'llama-3.1-8b-instant',          # Fast fallback
            'gemma2-9b-it',                  # Google's Gemma
            'mixtral-8x7b-32768',            # Mixtral - long context
        ]
        
        # ===== OPENROUTER (Fallback) =====
        self.api_key = os.getenv('OPENROUTER_API_KEY', '').strip()
        env_model = os.getenv('OPENROUTER_MODEL', '').strip()
        self.fallback_models = [
            env_model if env_model else None,
            'meta-llama/llama-3.3-70b-instruct:free',
            'deepseek/deepseek-chat-v3-0324:free',
            'deepseek/deepseek-r1:free',
            'qwen/qwen3-235b-a22b:free',
            'meta-llama/llama-3.2-3b-instruct:free',
            'mistralai/mistral-7b-instruct:free',
            'google/gemma-2-9b-it:free',
        ]
        seen = set()
        self.fallback_models = [m for m in self.fallback_models 
                                if m and not (m in seen or seen.add(m))]
        self.model = self.fallback_models[0] if self.fallback_models else None
        self.base_url = "https://openrouter.ai/api/v1"
        
        if self.groq_api_key:
            print(f"🚀 Groq enabled - {len(self.groq_models)} models")
        else:
            print("⚠️  GROQ_API_KEY not set - using OpenRouter only")
        print(f"OpenRouter fallback: {len(self.fallback_models)} models")
        
    def _call_groq(self, prompt: str) -> Dict[str, str]:
        """Try Groq models in order. Returns parsed dict or None on total failure."""
        if not self.groq_api_key:
            return None
        for model in self.groq_models:
            try:
                print(f"🚀 Trying Groq: {model}")
                response = requests.post(
                    self.groq_url,
                    headers={
                        'Authorization': f'Bearer {self.groq_api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': model,
                        'messages': [
                            {'role': 'system', 'content': 'You are a professional museum curator and historian who writes detailed, engaging Facebook posts about historical images. Always follow the exact output format requested.'},
                            {'role': 'user', 'content': prompt}
                        ],
                        'max_tokens': 2000,
                        'temperature': 0.75,
                    },
                    timeout=30
                )
                if response.status_code in (400, 401, 402, 404, 408, 429, 500, 502, 503, 504):
                    print(f"  Groq {model} returned {response.status_code}, trying next...")
                    continue
                response.raise_for_status()
                result = response.json()
                if 'choices' not in result or not result['choices']:
                    continue
                content = result['choices'][0]['message']['content']
                if not content or len(content) < 100:
                    continue
                print(f"✅ Got response from Groq: {model}")
                return self._parse_response(content)
            except Exception as e:
                print(f"  Groq {model} error: {e}")
                continue
        return None
    
    def generate_description(self, image_context: str) -> Dict[str, str]:
        """Generate image description and hashtags - try Groq first, then OpenRouter"""
        
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
        
        # ===== TIER 1: Try Groq first (fastest, best free tier) =====
        groq_result = self._call_groq(prompt)
        if groq_result and groq_result.get('description') and len(groq_result.get('description', '')) > 100:
            return groq_result
        
        if not self.api_key:
            print("⚠️  No OpenRouter API key - using fallback caption")
            return {
                'description': 'A remarkable image from the public domain archives, preserved for future generations.',
                'hashtags': '#publicdomain #art #history #culture #archives #heritage',
                'title': 'Historical Image'
            }
        
        # ===== TIER 2: OpenRouter fallback chain =====
        print("\n📡 Falling back to OpenRouter...")
        last_error = None
        for attempt_model in self.fallback_models:
            try:
                print(f"Trying model: {attempt_model}")
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        'model': attempt_model,
                        'messages': [
                            {'role': 'system', 'content': 'You are a helpful social media content creator.'},
                            {'role': 'user', 'content': prompt}
                        ],
                        'max_tokens': 1500,
                        'temperature': 0.75
                    },
                    timeout=45
                )
                
                # If rate-limited, not found, or server error, try next model
                if response.status_code in (400, 402, 404, 408, 429, 500, 502, 503, 504):
                    print(f"  Model {attempt_model} returned {response.status_code}, trying next...")
                    last_error = f"HTTP {response.status_code}"
                    continue
                
                response.raise_for_status()
                result = response.json()
                # Check if response has expected structure
                if 'choices' not in result or not result['choices']:
                    print(f"  {attempt_model} returned unexpected structure, trying next...")
                    continue
                content = result['choices'][0]['message']['content']
                if not content or len(content) < 50:
                    print(f"  {attempt_model} returned empty/short response, trying next...")
                    continue
                print(f"✅ Got response from: {attempt_model}")
                return self._parse_response(content)
                
            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code in (400, 402, 404, 408, 429, 500, 502, 503, 504):
                    print(f"  {attempt_model} HTTP {code}, trying next...")
                    last_error = e
                    continue
                last_error = e
                continue
            except Exception as e:
                last_error = e
                print(f"  Error with {attempt_model}: {e}")
                continue
        
        # All models failed - return fallback
        try:
            raise last_error if last_error else Exception("All models failed")
        except Exception as e:
            print(f"Error generating description (all fallbacks exhausted): {e}")
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
