import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

class TokenManager:
    """Automatic token rotation and management system"""
    
    def __init__(self, db_path: str = 'token_manager.db'):
        self.db_path = db_path
        self._init_database()
        
    def _init_database(self):
        """Initialize token management database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                token_type TEXT,
                token_value TEXT,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP,
                last_used TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id INTEGER,
                action TEXT,
                success BOOLEAN,
                timestamp TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS refresh_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                old_token_id INTEGER,
                new_token_id INTEGER,
                refresh_method TEXT,
                timestamp TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def store_token(self, platform: str, token_type: str, token_value: str, 
                   expires_in_days: int = 60) -> int:
        """Store a new token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        expires_at = datetime.now() + timedelta(days=expires_in_days)
        
        cursor.execute('''
            INSERT INTO tokens (platform, token_type, token_value, expires_at, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (platform, token_type, token_value, expires_at, datetime.now()))
        
        token_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return token_id
    
    def get_active_token(self, platform: str, token_type: str = 'access') -> Optional[Dict]:
        """Get active token that's not expired"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, platform, token_type, token_value, expires_at, last_used
            FROM tokens
            WHERE platform = ? AND token_type = ? AND is_active = 1 AND expires_at > datetime('now')
            ORDER BY last_used DESC
            LIMIT 1
        ''', (platform, token_type))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'id': result[0],
                'platform': result[1],
                'token_type': result[2],
                'token_value': result[3],
                'expires_at': result[4],
                'last_used': result[5]
            }
        
        return None
    
    def mark_token_used(self, token_id: int, success: bool = True):
        """Mark token as used"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE tokens SET last_used = datetime('now') WHERE id = ?
        ''', (token_id,))
        
        cursor.execute('''
            INSERT INTO token_usage_log (token_id, action, success, timestamp)
            VALUES (?, 'api_call', ?, datetime('now'))
        ''', (token_id, success))
        
        conn.commit()
        conn.close()
    
    def deactivate_token(self, token_id: int):
        """Deactivate a token"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE tokens SET is_active = 0 WHERE id = ?', (token_id,))
        conn.commit()
        conn.close()
    
    def check_token_expiry(self, platform: str, days_before: int = 7) -> List[Dict]:
        """Check for tokens expiring soon"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        expiry_threshold = datetime.now() + timedelta(days=days_before)
        
        cursor.execute('''
            SELECT id, platform, token_type, expires_at
            FROM tokens
            WHERE platform = ? AND is_active = 1 AND expires_at < ?
            ORDER BY expires_at ASC
        ''', (platform, expiry_threshold))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'id': row[0],
                'platform': row[1],
                'token_type': row[2],
                'expires_at': row[3],
                'days_until_expiry': (datetime.fromisoformat(row[3]) - datetime.now()).days
            })
        
        conn.close()
        return results
    
    def refresh_facebook_token(self) -> bool:
        """Attempt to refresh Facebook token"""
        try:
            # Facebook tokens need manual refresh through their UI
            # This function logs the need for refresh
            print("⚠️  Facebook token needs manual refresh")
            print("Please visit: https://developers.facebook.com/tools/explorer/")
            return False
        except Exception as e:
            print(f"Token refresh error: {e}")
            return False
    
    def auto_rotate_tokens(self) -> Dict:
        """Automatically rotate tokens that are expiring"""
        results = {'rotated': [], 'failed': []}
        
        # Check Facebook tokens
        expiring_fb = self.check_token_expiry('facebook', days_before=7)
        for token in expiring_fb:
            if self.refresh_facebook_token():
                results['rotated'].append(token)
            else:
                results['failed'].append(token)
        
        return results
    
    def get_token_stats(self) -> Dict:
        """Get token usage statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total tokens
        cursor.execute('SELECT COUNT(*) FROM tokens WHERE is_active = 1')
        total_active = cursor.fetchone()[0]
        
        # Expiring soon
        cursor.execute('''
            SELECT COUNT(*) FROM tokens 
            WHERE is_active = 1 AND expires_at < datetime('now', '+7 days')
        ''')
        expiring_soon = cursor.fetchone()[0]
        
        # Usage stats
        cursor.execute('''
            SELECT token_id, COUNT(*) as call_count, 
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
            FROM token_usage_log
            WHERE timestamp > datetime('now', '-24 hours')
            GROUP BY token_id
        ''')
        
        usage_stats = []
        for row in cursor.fetchall():
            usage_stats.append({
                'token_id': row[0],
                'call_count': row[1],
                'success_count': row[2],
                'success_rate': row[2] / row[1] if row[1] > 0 else 0
            })
        
        conn.close()
        
        return {
            'total_active_tokens': total_active,
            'expiring_soon': expiring_soon,
            'usage_stats_24h': usage_stats
        }


class IntelligentScheduler:
    """AI-powered scheduling based on audience engagement patterns"""
    
    def __init__(self, db_path: str = 'scheduler.db'):
        self.db_path = db_path
        self._init_database()
        
        # Default optimal posting times (can be learned)
        self.optimal_times = {
            'weekday': [9, 12, 15, 18, 21],  # 9am, 12pm, 3pm, 6pm, 9pm
            'weekend': [10, 13, 16, 19, 22]
        }
        
    def _init_database(self):
        """Initialize scheduler database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                posted_at TIMESTAMP,
                engagement_score REAL,
                day_of_week INTEGER,
                hour INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS engagement_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER,
                metric_type TEXT,
                metric_value REAL,
                recorded_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_optimizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER,
                hour INTEGER,
                avg_engagement REAL,
                sample_size INTEGER
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_post(self, platform: str, posted_at: datetime):
        """Record a post for learning"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO posts (platform, posted_at, day_of_week, hour)
            VALUES (?, ?, ?, ?)
        ''', (platform, posted_at, posted_at.weekday(), posted_at.hour))
        
        conn.commit()
        conn.close()
    
    def record_engagement(self, post_id: int, metrics: Dict):
        """Record engagement metrics for a post"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for metric_type, metric_value in metrics.items():
            cursor.execute('''
                INSERT INTO engagement_data (post_id, metric_type, metric_value, recorded_at)
                VALUES (?, ?, ?, datetime('now'))
            ''', (post_id, metric_type, metric_value))
        
        conn.commit()
        conn.close()
    
    def calculate_optimal_times(self, platform: str = 'facebook') -> Dict:
        """Calculate optimal posting times based on historical data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get engagement by day and hour
        cursor.execute('''
            SELECT day_of_week, hour, AVG(engagement_score) as avg_engagement, COUNT(*) as count
            FROM posts
            WHERE platform = ? AND engagement_score IS NOT NULL
            GROUP BY day_of_week, hour
            HAVING count >= 3
            ORDER BY avg_engagement DESC
            LIMIT 20
        ''', (platform,))
        
        optimal_slots = []
        for row in cursor.fetchall():
            optimal_slots.append({
                'day_of_week': row[0],
                'hour': row[1],
                'avg_engagement': row[2],
                'sample_size': row[3]
            })
        
        conn.close()
        
        return {
            'learned_optimal_times': optimal_slots if optimal_slots else None,
            'default_times': self.optimal_times
        }
    
    def get_next_optimal_time(self, platform: str = 'facebook', 
                             min_hours_from_now: int = 1,
                             max_hours_from_now: int = 12) -> datetime:
        """Get next optimal posting time"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        optimal_data = self.calculate_optimal_times(platform)
        
        # Use learned times if available, otherwise use defaults
        times_to_check = optimal_data['learned_optimal_times'] if optimal_data['learned_optimal_times'] else []
        
        if not times_to_check:
            # Use default times
            day_type = 'weekend' if now.weekday() >= 5 else 'weekday'
            times_to_check = [{'hour': h} for h in self.optimal_times[day_type]]
        
        # Find next optimal time within range
        for hours_ahead in range(min_hours_from_now, max_hours_from_now + 1):
            candidate_time = now + timedelta(hours=hours_ahead)
            candidate_hour = candidate_time.hour
            
            # Check if this hour is in optimal times
            for slot in times_to_check:
                if slot.get('hour') == candidate_hour:
                    return candidate_time
        
        # Fallback to random time in range
        random_hours = random.randint(min_hours_from_now, max_hours_from_now)
        return now + timedelta(hours=random_hours)
    
    def learn_from_engagement(self):
        """Update optimal times based on engagement data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate average engagement by day/hour
        cursor.execute('''
            INSERT OR REPLACE INTO schedule_optimizations (day_of_week, hour, avg_engagement, sample_size)
            SELECT day_of_week, hour, AVG(engagement_score), COUNT(*)
            FROM posts
            WHERE engagement_score IS NOT NULL
            GROUP BY day_of_week, hour
        ''')
        
        conn.commit()
        conn.close()
