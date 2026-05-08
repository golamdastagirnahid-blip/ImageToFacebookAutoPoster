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
    
    def post_image(self, image_path: str, caption: str, image_url: str = None) -> Dict:
        """Post a single image to Facebook. Tries URL upload first, falls back to file upload."""
        upload_url = f"{self.base_url}/{self.page_id}/photos"
        
        # Try posting via URL first (more reliable for Facebook)
        if image_url:
            try:
                data = {
                    'url': image_url,
                    'caption': caption,
                    'access_token': self.access_token,
                    'published': 'true'
                }
                response = requests.post(upload_url, data=data, timeout=60)
                response.raise_for_status()
                result = response.json()
                print(f"Successfully posted image via URL. Post ID: {result.get('id')}")
                return result
            except Exception as e:
                print(f"URL upload failed, trying file upload: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Response: {e.response.text}")
        
        # Fallback: file upload
        try:
            with open(image_path, 'rb') as image_file:
                files = {'source': image_file}
                data = {
                    'caption': caption,
                    'access_token': self.access_token,
                    'published': 'true'
                }
                
                response = requests.post(upload_url, files=files, data=data, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                print(f"Successfully posted image via file. Post ID: {result.get('id')}")
                return result
                
        except Exception as e:
            print(f"Error posting to Facebook: {e}")
            if hasattr(e, 'response') and e.response is not None:
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
            # Also check token expiry
            self.check_token_expiry()
            return True
        except Exception as e:
            print(f"Facebook API connection failed: {e}")
            return False
    
    def check_token_expiry(self) -> dict:
        """Check when the FB access token expires and warn if soon."""
        try:
            from datetime import datetime
            url = f"{self.base_url}/debug_token"
            params = {
                'input_token': self.access_token,
                'access_token': self.access_token
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json().get('data', {})
            expires_at = data.get('expires_at', 0)
            
            if expires_at == 0:
                print("✅ Token is long-lived (never expires)")
                return {'expires_at': 0, 'days_remaining': -1, 'never_expires': True}
            
            now = int(datetime.now().timestamp())
            days_left = (expires_at - now) / 86400
            
            if days_left < 7:
                print(f"🚨 CRITICAL: FB token expires in {days_left:.1f} DAYS!")
                print("   → Renew immediately at: https://developers.facebook.com/tools/explorer/")
            elif days_left < 14:
                print(f"⚠️  WARNING: FB token expires in {days_left:.1f} days. Renew soon.")
            elif days_left < 30:
                print(f"ℹ️  FB token expires in {days_left:.1f} days.")
            else:
                print(f"✅ FB token valid for {days_left:.0f} more days")
            
            return {
                'expires_at': expires_at,
                'days_remaining': days_left,
                'never_expires': False,
                'critical': days_left < 7,
                'warning': days_left < 14
            }
        except Exception as e:
            print(f"Token expiry check failed (non-fatal): {e}")
            return {'error': str(e)}
