import requests
import os
from typing import Dict, List
from dotenv import load_dotenv

load_dotenv()

class FacebookPoster:
    def __init__(self):
        self.access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.page_id = os.getenv('FACEBOOK_PAGE_ID')
        self.api_version = 'v18.0'
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        
        if not self.access_token or not self.page_id:
            raise ValueError("FACEBOOK_ACCESS_TOKEN and FACEBOOK_PAGE_ID must be set")
    
    def post_image(self, image_path: str, caption: str) -> Dict:
        """Post a single image to Facebook"""
        try:
            # First, upload the image
            upload_url = f"{self.base_url}/{self.page_id}/photos"
            
            with open(image_path, 'rb') as image_file:
                files = {'source': image_file}
                data = {
                    'caption': caption,
                    'access_token': self.access_token,
                    'published': True
                }
                
                response = requests.post(upload_url, files=files, data=data, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                print(f"Successfully posted image. Post ID: {result.get('id')}")
                return result
                
        except Exception as e:
            print(f"Error posting to Facebook: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return {'error': str(e)}
    
    def post_multiple_images(self, image_paths: List[str], caption: str) -> Dict:
        """Post multiple images as a carousel to Facebook"""
        try:
            # Upload images first to get their IDs
            uploaded_ids = []
            
            for image_path in image_paths:
                upload_url = f"{self.base_url}/{self.page_id}/photos"
                
                with open(image_path, 'rb') as image_file:
                    files = {'source': image_file}
                    data = {
                        'access_token': self.access_token,
                        'published': False  # Don't publish yet
                    }
                    
                    response = requests.post(upload_url, files=files, data=data, timeout=60)
                    response.raise_for_status()
                    
                    result = response.json()
                    uploaded_ids.append(result['id'])
            
            # Create the post with uploaded images
            post_url = f"{self.base_url}/{self.page_id}/feed"
            import json
            data = {
                'message': caption,
                'access_token': self.access_token,
            }
            # attached_media must be passed as individual JSON-encoded fields
            for i, img_id in enumerate(uploaded_ids):
                data[f'attached_media[{i}]'] = json.dumps({'media_fbid': img_id})
            
            response = requests.post(post_url, data=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            print(f"Successfully posted carousel. Post ID: {result.get('id')}")
            return result
            
        except Exception as e:
            print(f"Error posting carousel to Facebook: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            return {'error': str(e)}
    
    def test_connection(self) -> bool:
        """Test if the Facebook API connection works"""
        try:
            test_url = f"{self.base_url}/{self.page_id}"
            params = {'access_token': self.access_token}
            response = requests.get(test_url, params=params, timeout=10)
            response.raise_for_status()
            print("Facebook API connection successful!")
            return True
        except Exception as e:
            print(f"Facebook API connection failed: {e}")
            return False
