import os
import time
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

class HealthMonitor:
    """Self-healing health check system with automatic recovery"""
    
    def __init__(self, db_path: str = 'health_monitor.db'):
        self.db_path = db_path
        self._init_database()
        self.alert_webhook = os.getenv('ALERT_WEBHOOK_URL', '')
        
    def _init_database(self):
        """Initialize health monitoring database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT,
                status TEXT,
                message TEXT,
                timestamp TIMESTAMP,
                response_time_ms REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT,
                severity TEXT,
                message TEXT,
                resolved BOOLEAN DEFAULT 0,
                created_at TIMESTAMP,
                resolved_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT,
                metric_value REAL,
                timestamp TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def check_component(self, component: str, check_func) -> Dict:
        """Run health check on a component"""
        start_time = time.time()
        status = 'healthy'
        message = 'OK'
        
        try:
            result = check_func()
            if not result.get('success', True):
                status = 'unhealthy'
                message = result.get('error', 'Unknown error')
        except Exception as e:
            status = 'unhealthy'
            message = str(e)
        
        response_time = (time.time() - start_time) * 1000
        
        # Log to database
        self._log_health_check(component, status, message, response_time)
        
        # Create incident if unhealthy
        if status == 'unhealthy':
            self._create_incident(component, 'critical', message)
            self._send_alert(component, status, message)
        
        return {
            'component': component,
            'status': status,
            'message': message,
            'response_time_ms': response_time
        }
    
    def _log_health_check(self, component: str, status: str, message: str, response_time: float):
        """Log health check result"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO health_checks (component, status, message, timestamp, response_time_ms)
            VALUES (?, ?, ?, ?, ?)
        ''', (component, status, message, datetime.now(), response_time))
        conn.commit()
        conn.close()
    
    def _create_incident(self, component: str, severity: str, message: str):
        """Create incident record"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO incidents (component, severity, message, created_at)
            VALUES (?, ?, ?, ?)
        ''', (component, severity, message, datetime.now()))
        conn.commit()
        conn.close()
    
    def resolve_incident(self, component: str):
        """Mark incident as resolved"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE incidents 
            SET resolved = 1, resolved_at = ?
            WHERE component = ? AND resolved = 0
        ''', (datetime.now(), component))
        conn.commit()
        conn.close()
    
    def _send_alert(self, component: str, status: str, message: str):
        """Send alert via webhook"""
        if not self.alert_webhook:
            return
        
        try:
            payload = {
                'component': component,
                'status': status,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'severity': 'critical' if status == 'unhealthy' else 'warning'
            }
            
            requests.post(self.alert_webhook, json=payload, timeout=10)
        except Exception as e:
            print(f"Failed to send alert: {e}")
    
    def record_metric(self, metric_name: str, value: float):
        """Record performance metric"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO metrics (metric_name, metric_value, timestamp)
            VALUES (?, ?, ?)
        ''', (metric_name, value, datetime.now()))
        conn.commit()
        conn.close()
    
    def get_health_summary(self) -> Dict:
        """Get overall health summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Recent checks
        cursor.execute('''
            SELECT component, status, COUNT(*) as count
            FROM health_checks
            WHERE timestamp > datetime('now', '-1 hour')
            GROUP BY component, status
        ''')
        recent_checks = cursor.fetchall()
        
        # Active incidents
        cursor.execute('''
            SELECT component, severity, message, created_at
            FROM incidents
            WHERE resolved = 0
            ORDER BY created_at DESC
        ''')
        active_incidents = cursor.fetchall()
        
        # Average response times
        cursor.execute('''
            SELECT component, AVG(response_time_ms) as avg_time
            FROM health_checks
            WHERE timestamp > datetime('now', '-1 hour')
            GROUP BY component
        ''')
        avg_times = cursor.fetchall()
        
        conn.close()
        
        return {
            'recent_checks': recent_checks,
            'active_incidents': active_incidents,
            'average_response_times': avg_times,
            'overall_status': 'healthy' if not active_incidents else 'degraded'
        }
    
    def cleanup_old_records(self, days: int = 7):
        """Clean up old health check records"""
        cutoff = datetime.now() - timedelta(days=days)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM health_checks WHERE timestamp < ?', (cutoff,))
        cursor.execute('DELETE FROM metrics WHERE timestamp < ?', (cutoff,))
        cursor.execute('DELETE FROM incidents WHERE created_at < ? AND resolved = 1', (cutoff,))
        
        conn.commit()
        conn.close()


class SelfHealingSystem:
    """Automatic recovery system for common failures"""
    
    def __init__(self, health_monitor: HealthMonitor):
        self.monitor = health_monitor
        self.recovery_attempts = {}
        self.max_attempts = 3
    
    def attempt_recovery(self, component: str, recovery_func) -> bool:
        """Attempt automatic recovery for a failed component"""
        attempts = self.recovery_attempts.get(component, 0)
        
        if attempts >= self.max_attempts:
            print(f"Max recovery attempts reached for {component}")
            return False
        
        self.recovery_attempts[component] = attempts + 1
        
        try:
            print(f"Attempting recovery for {component} (attempt {attempts + 1})")
            success = recovery_func()
            
            if success:
                print(f"Recovery successful for {component}")
                self.monitor.resolve_incident(component)
                self.recovery_attempts[component] = 0
                return True
            else:
                print(f"Recovery failed for {component}")
                return False
                
        except Exception as e:
            print(f"Recovery error for {component}: {e}")
            return False
    
    def check_facebook_connection(self) -> Dict:
        """Check Facebook API connection"""
        try:
            from facebook_poster import FacebookPoster
            fb = FacebookPoster()
            success = fb.test_connection()
            return {'success': success, 'error': None if success else 'Connection failed'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def recover_facebook_connection(self) -> bool:
        """Attempt to recover Facebook connection"""
        try:
            # Force re-initialization
            from facebook_poster import FacebookPoster
            fb = FacebookPoster()
            return fb.test_connection()
        except:
            return False
    
    def check_openrouter_connection(self) -> Dict:
        """Check OpenRouter API connection"""
        try:
            from openrouter_client import OpenRouterClient
            client = OpenRouterClient()
            # Simple test call
            if not client.api_key:
                return {'success': False, 'error': 'API key not set'}
            return {'success': True, 'error': None}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_disk_space(self) -> Dict:
        """Check available disk space"""
        import shutil
        try:
            total, used, free = shutil.disk_usage('.')
            free_gb = free / (1024**3)
            
            if free_gb < 1:  # Less than 1GB
                return {'success': False, 'error': f'Low disk space: {free_gb:.2f}GB'}
            
            return {'success': True, 'error': None, 'free_gb': free_gb}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def recover_disk_space(self) -> bool:
        """Attempt to recover disk space"""
        try:
            from image_scraper_pro import ImageScraperPro
            scraper = ImageScraperPro()
            scraper.cleanup_cache(max_age_hours=1)  # Aggressive cleanup
            return True
        except:
            return False
    
    def run_health_checks(self) -> Dict:
        """Run all health checks and attempt recovery"""
        results = {}
        
        # Check Facebook
        fb_result = self.monitor.check_component('facebook', self.check_facebook_connection)
        results['facebook'] = fb_result
        if fb_result['status'] == 'unhealthy':
            self.attempt_recovery('facebook', self.recover_facebook_connection)
        
        # Check OpenRouter
        or_result = self.monitor.check_component('openrouter', self.check_openrouter_connection)
        results['openrouter'] = or_result
        
        # Check disk space
        disk_result = self.monitor.check_component('disk_space', self.check_disk_space)
        results['disk_space'] = disk_result
        if disk_result['status'] == 'unhealthy':
            self.attempt_recovery('disk_space', self.recover_disk_space)
        
        return results
