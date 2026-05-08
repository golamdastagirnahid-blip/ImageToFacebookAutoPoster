import os
import requests
from typing import Dict, List, Optional
from PIL import Image
from io import BytesIO
import re
from dotenv import load_dotenv

load_dotenv()

class ContentFilter:
    """NSFW and inappropriate content detection"""
    
    def __init__(self):
        self.nsfw_keywords = self._load_nsfw_keywords()
        self.use_ai_filter = os.getenv('USE_AI_CONTENT_FILTER', 'false').lower() == 'true'
        
    def _load_nsfw_keywords(self) -> List[str]:
        """Load list of NSFW keywords for text filtering"""
        return [
            'nude', 'naked', 'porn', 'sex', 'explicit', 'adult',
            'erotic', 'fetish', 'nsfw', 'xxx', 'breast', 'genital',
            'sexual', 'intimate', 'provocative', 'suggestive'
        ]
    
    def check_text_content(self, text: str) -> Dict:
        """Check text content for inappropriate material"""
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in self.nsfw_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        is_safe = len(found_keywords) == 0
        
        return {
            'safe': is_safe,
            'found_keywords': found_keywords,
            'confidence': 1.0 if is_safe else 0.0
        }
    
    def check_image_content(self, image_path: str) -> Dict:
        """Check image content for inappropriate material"""
        try:
            # Basic image analysis
            img = Image.open(image_path)
            width, height = img.size
            aspect_ratio = width / height
            
            # Check for suspicious aspect ratios (often NSFW content has specific ratios)
            suspicious_ratios = [0.5, 0.6, 0.7, 1.4, 1.5, 2.0]
            ratio_suspicious = any(abs(aspect_ratio - r) < 0.1 for r in suspicious_ratios)
            
            # Check image properties
            is_very_small = width < 200 or height < 200
            is_very_large = width > 4000 or height > 4000
            
            # Basic safety score
            safety_score = 100
            if ratio_suspicious:
                safety_score -= 20
            if is_very_small:
                safety_score -= 10
            if is_very_large:
                safety_score -= 5
            
            # If AI filter is enabled, use it
            if self.use_ai_filter:
                ai_result = self._ai_image_check(image_path)
                safety_score = min(safety_score, ai_result.get('safety_score', 50))
            
            is_safe = safety_score >= 70
            
            return {
                'safe': is_safe,
                'safety_score': safety_score,
                'aspect_ratio': aspect_ratio,
                'dimensions': (width, height),
                'ai_checked': self.use_ai_filter
            }
            
        except Exception as e:
            print(f"Error checking image content: {e}")
            return {'safe': False, 'error': str(e)}
    
    def _ai_image_check(self, image_path: str) -> Dict:
        """Use AI to check image content (requires external service)"""
        # This would integrate with services like:
        # - Google Cloud Vision API
        # - AWS Rekognition
        # - Azure Computer Vision
        # - OpenAI Vision API
        
        # For now, return conservative default
        return {
            'safety_score': 85,
            'adult_content': False,
            'violence': False,
            'racy': False
        }
    
    def check_url_content(self, url: str) -> Dict:
        """Check URL for inappropriate content"""
        # Check URL path and parameters
        url_lower = url.lower()
        
        suspicious_patterns = [
            'nsfw', 'porn', 'xxx', 'adult', 'erotic', 'nude',
            'sex', 'fetish', 'explicit'
        ]
        
        found_patterns = [p for p in suspicious_patterns if p in url_lower]
        
        return {
            'safe': len(found_patterns) == 0,
            'found_patterns': found_patterns
        }
    
    def comprehensive_check(self, image_info: Dict) -> Dict:
        """Run comprehensive content check"""
        results = {
            'overall_safe': True,
            'checks': {}
        }
        
        # Check URL
        url_check = self.check_url_content(image_info.get('url', ''))
        results['checks']['url'] = url_check
        if not url_check['safe']:
            results['overall_safe'] = False
        
        # Check text metadata
        text_to_check = f"{image_info.get('title', '')} {image_info.get('alt_text', '')}"
        text_check = self.check_text_content(text_to_check)
        results['checks']['text'] = text_check
        if not text_check['safe']:
            results['overall_safe'] = False
        
        # Check image if local path available
        if image_info.get('local_path'):
            image_check = self.check_image_content(image_info['local_path'])
            results['checks']['image'] = image_check
            if not image_check['safe']:
                results['overall_safe'] = False
        
        return results


class RateLimiter:
    """Intelligent rate limiting with backoff strategies"""
    
    def __init__(self, db_path: str = 'rate_limiter.db'):
        self.db_path = db_path
        self._init_database()
        
        # Rate limits (requests per minute)
        self.limits = {
            'facebook_api': 200,  # 200 per minute
            'archive_scrape': 30,  # 30 per minute
            'openrouter_api': 20,  # 20 per minute
            'default': 60  # 60 per minute
        }
    
    def _init_database(self):
        """Initialize rate limiting database"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rate_limits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                endpoint TEXT,
                timestamp TIMESTAMP,
                success BOOLEAN
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backoff_states (
                endpoint TEXT PRIMARY KEY,
                backoff_until TIMESTAMP,
                retry_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def check_rate_limit(self, endpoint: str) -> Dict:
        """Check if request is allowed"""
        import sqlite3
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if in backoff
        cursor.execute('SELECT backoff_until, retry_count FROM backoff_states WHERE endpoint = ?', (endpoint,))
        backoff = cursor.fetchone()
        
        if backoff:
            backoff_until = datetime.fromisoformat(backoff[0])
            if datetime.now() < backoff_until:
                wait_seconds = (backoff_until - datetime.now()).total_seconds()
                conn.close()
                return {
                    'allowed': False,
                    'reason': 'backoff',
                    'wait_seconds': wait_seconds,
                    'retry_count': backoff[1]
                }
        
        # Check rate limit
        limit = self.limits.get(endpoint, self.limits['default'])
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        
        cursor.execute('''
            SELECT COUNT(*) FROM rate_limits
            WHERE endpoint = ? AND timestamp > ?
        ''', (endpoint, one_minute_ago))
        
        count = cursor.fetchone()[0]
        
        conn.close()
        
        if count >= limit:
            return {
                'allowed': False,
                'reason': 'rate_limit',
                'limit': limit,
                'current': count
            }
        
        return {'allowed': True}
    
    def record_request(self, endpoint: str, success: bool = True):
        """Record a request"""
        import sqlite3
        from datetime import datetime
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO rate_limits (endpoint, timestamp, success)
            VALUES (?, ?, ?)
        ''', (endpoint, datetime.now(), success))
        conn.commit()
        conn.close()
    
    def trigger_backoff(self, endpoint: str, initial_delay: int = 60):
        """Trigger exponential backoff"""
        import sqlite3
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current retry count
        cursor.execute('SELECT retry_count FROM backoff_states WHERE endpoint = ?', (endpoint,))
        result = cursor.fetchone()
        retry_count = result[0] if result else 0
        
        # Calculate backoff time (exponential)
        backoff_seconds = initial_delay * (2 ** retry_count)
        backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
        
        # Update or insert backoff state
        cursor.execute('''
            INSERT OR REPLACE INTO backoff_states (endpoint, backoff_until, retry_count)
            VALUES (?, ?, ?)
        ''', (endpoint, backoff_until.isoformat(), retry_count + 1))
        
        conn.commit()
        conn.close()
        
        return backoff_seconds
    
    def clear_backoff(self, endpoint: str):
        """Clear backoff state after successful request"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM backoff_states WHERE endpoint = ?', (endpoint,))
        conn.commit()
        conn.close()
    
    def get_status(self) -> Dict:
        """Get current rate limiting status"""
        import sqlite3
        from datetime import datetime, timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get recent request counts
        one_minute_ago = datetime.now() - timedelta(minutes=1)
        cursor.execute('''
            SELECT endpoint, COUNT(*) as count
            FROM rate_limits
            WHERE timestamp > ?
            GROUP BY endpoint
        ''', (one_minute_ago,))
        
        recent_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get active backoffs
        cursor.execute('SELECT endpoint, backoff_until, retry_count FROM backoff_states')
        active_backoffs = []
        for row in cursor.fetchall():
            backoff_until = datetime.fromisoformat(row[1])
            if datetime.now() < backoff_until:
                active_backoffs.append({
                    'endpoint': row[0],
                    'backoff_until': row[1],
                    'retry_count': row[2],
                    'wait_seconds': (backoff_until - datetime.now()).total_seconds()
                })
        
        conn.close()
        
        return {
            'recent_counts': recent_counts,
            'active_backoffs': active_backoffs,
            'limits': self.limits
        }
