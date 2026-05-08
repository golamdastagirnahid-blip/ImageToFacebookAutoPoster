import os
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

class NotificationSystem:
    """Multi-channel notification system for alerts and updates"""
    
    def __init__(self):
        self.discord_webhook = os.getenv('DISCORD_WEBHOOK_URL', '')
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL', '')
        self.email_enabled = os.getenv('EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
        self.email_to = os.getenv('EMAIL_TO', '')
        
    def send_discord(self, title: str, message: str, color: int = 0x00ff00) -> bool:
        """Send notification to Discord"""
        if not self.discord_webhook:
            return False
        
        try:
            payload = {
                'embeds': [{
                    'title': title,
                    'description': message,
                    'color': color,
                    'timestamp': datetime.now().isoformat()
                }]
            }
            
            response = requests.post(self.discord_webhook, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Discord notification failed: {e}")
            return False
    
    def send_slack(self, title: str, message: str, color: str = 'good') -> bool:
        """Send notification to Slack"""
        if not self.slack_webhook:
            return False
        
        try:
            payload = {
                'attachments': [{
                    'title': title,
                    'text': message,
                    'color': color,
                    'ts': int(datetime.now().timestamp())
                }]
            }
            
            response = requests.post(self.slack_webhook, json=payload, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Slack notification failed: {e}")
            return False
    
    def send_email(self, subject: str, message: str) -> bool:
        """Send email notification (requires SMTP configuration)"""
        if not self.email_enabled or not self.email_to:
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME', '')
            smtp_password = os.getenv('SMTP_PASSWORD', '')
            
            if not smtp_username or not smtp_password:
                return False
            
            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = self.email_to
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email notification failed: {e}")
            return False
    
    def notify_success(self, post_id: str, platform: str = 'facebook'):
        """Send success notification"""
        message = f"✅ Post successfully published to {platform}\nPost ID: {post_id}"
        
        self.send_discord('Post Success', message, color=0x00ff00)
        self.send_slack('Post Success', message, color='good')
    
    def notify_failure(self, error: str, component: str = 'system'):
        """Send failure notification"""
        message = f"❌ Error in {component}\n{error}"
        
        self.send_discord('System Error', message, color=0xff0000)
        self.send_slack('System Error', message, color='danger')
        self.send_email(f'Automation Error: {component}', message)
    
    def notify_health_check(self, health_status: Dict):
        """Send health check notification"""
        if health_status.get('overall_status') == 'healthy':
            return  # Don't notify for healthy status
        
        message = f"⚠️ System Health: {health_status.get('overall_status')}\n"
        message += f"Active Incidents: {len(health_status.get('active_incidents', []))}\n"
        
        for incident in health_status.get('active_incidents', []):
            message += f"- {incident[0]}: {incident[2]}\n"
        
        self.send_discord('Health Alert', message, color=0xffff00)
        self.send_slack('Health Alert', message, color='warning')
    
    def notify_token_expiry(self, platform: str, days_remaining: int):
        """Send token expiry warning"""
        message = f"⚠️ Token expiring soon for {platform}\nDays remaining: {days_remaining}\nPlease refresh the token."
        
        self.send_discord('Token Expiry Warning', message, color=0xffff00)
        self.send_slack('Token Expiry Warning', message, color='warning')
        self.send_email(f'Token Expiry Warning: {platform}', message)
    
    def notify_rate_limit(self, endpoint: str, wait_seconds: int):
        """Send rate limit notification"""
        message = f"⚠️ Rate limit hit for {endpoint}\nWaiting {wait_seconds} seconds before retry."
        
        self.send_discord('Rate Limit Warning', message, color=0xffff00)
    
    def notify_analytics_report(self, report: Dict):
        """Send analytics summary"""
        message = f"📊 Weekly Analytics Report\n\n"
        
        daily_summary = report.get('daily_summary', [])
        if daily_summary:
            total_posts = sum(d['posts_count'] for d in daily_summary)
            message += f"Total Posts: {total_posts}\n"
        
        suggestions = report.get('optimization_suggestions', [])
        if suggestions:
            message += f"\nOptimization Suggestions:\n"
            for sugg in suggestions[:3]:
                message += f"- {sugg['suggestion']}\n"
        
        self.send_discord('Analytics Report', message, color=0x00bfff)
    
    def notify_content_flagged(self, image_url: str, reason: str):
        """Send notification when content is flagged"""
        message = f"🚩 Content flagged\nImage: {image_url}\nReason: {reason}"
        
        self.send_discord('Content Flagged', message, color=0xff0000)
        self.send_slack('Content Flagged', message, color='danger')
