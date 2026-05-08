import os
import random
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from image_scraper import ImageScraper
from image_scraper_pro import ImageScraperPro
from openrouter_client import OpenRouterClient
from facebook_poster import FacebookPoster
from health_monitor import HealthMonitor, SelfHealingSystem
from content_filter import ContentFilter, RateLimiter
from nsfw_detector import StrictNSFWDetector, FacebookPolicyCompliance
from token_manager import TokenManager, IntelligentScheduler
from analytics import AnalyticsEngine
from notification_system import NotificationSystem

load_dotenv()

class EnterpriseAutomation:
    """Enterprise-grade automation with all advanced features"""
    
    def __init__(self):
        print("🚀 Initializing Enterprise Automation System...")
        
        # Core components
        self.use_pro = os.getenv('USE_PRO_SCRAPER', 'true').lower() == 'true'
        if self.use_pro:
            print("✅ PRO image scraper enabled")
            self.scraper = ImageScraperPro()
        else:
            print("✅ Basic image scraper enabled")
            self.scraper = ImageScraper()
        
        self.openrouter = OpenRouterClient()
        self.facebook = FacebookPoster()
        
        # Enterprise components
        self.health_monitor = HealthMonitor()
        self.self_healing = SelfHealingSystem(self.health_monitor)
        self.content_filter = ContentFilter()
        self.nsfw_detector = StrictNSFWDetector()
        self.facebook_compliance = FacebookPolicyCompliance()
        self.rate_limiter = RateLimiter()
        self.token_manager = TokenManager()
        self.scheduler = IntelligentScheduler()
        self.analytics = AnalyticsEngine()
        self.notifications = NotificationSystem()
        
        # Configuration
        self.min_interval = int(os.getenv('MIN_POST_INTERVAL_HOURS', '4') or '4')
        self.max_interval = int(os.getenv('MAX_POST_INTERVAL_HOURS', '12') or '12')
        self.max_images_per_post = int(os.getenv('MAX_IMAGES_PER_POST', '3') or '3')
        self.sources = [s.strip() for s in os.getenv('ARCHIVE_SOURCES', '').split(',') if s.strip()]
        self.credit_template = os.getenv('CREDIT_TEXT', 'Image Source: {source}') or 'Image Source: {source}'
        self.disclaimer_template = os.getenv('DISCLAIMER_TEXT', 'Disclaimer: This image is used for commercial purposes under public domain or Creative Commons license.') or 'Disclaimer: This image is used for commercial purposes under public domain or Creative Commons license.'
        self.max_pages_per_source = int(os.getenv('MAX_PAGES_PER_SOURCE', '5') or '5')
        
        print("✅ All enterprise systems initialized\n")
    
    def pre_flight_checks(self) -> bool:
        """Run pre-flight health checks"""
        print("🔍 Running pre-flight checks...")
        
        # Health checks
        health_results = self.self_healing.run_health_checks()
        
        all_healthy = all(r['status'] == 'healthy' for r in health_results.values())
        
        if not all_healthy:
            print("⚠️  Some health checks failed")
            self.notifications.notify_health_check(self.health_monitor.get_health_summary())
        else:
            print("✅ All systems healthy")
        
        # Token expiry check
        expiring_tokens = self.token_manager.check_token_expiry('facebook', days_before=7)
        if expiring_tokens:
            print(f"⚠️  {len(expiring_tokens)} token(s) expiring soon")
            for token in expiring_tokens:
                self.notifications.notify_token_expiry('facebook', token['days_until_expiry'])
        
        # Rate limit check
        rate_status = self.rate_limiter.get_status()
        if rate_status['active_backoffs']:
            print(f"⚠️  {len(rate_status['active_backoffs'])} active rate limit backoffs")
        
        return all_healthy
    
    def generate_caption(self, image_info: dict, ai_content: dict) -> str:
        """Generate full caption with description, hashtags, credits, and disclaimer"""
        caption_parts = []
        
        if ai_content.get('title'):
            caption_parts.append(f"📌 {ai_content['title']}\n")
        
        if ai_content.get('description'):
            caption_parts.append(f"{ai_content['description']}\n")
        
        if ai_content.get('hashtags'):
            caption_parts.append(f"\n{ai_content['hashtags']}")
        
        credit = self.credit_template.format(source=image_info.get('source', 'Unknown'))
        caption_parts.append(f"\n\n{credit}")
        caption_parts.append(f"\n{self.disclaimer_template}")
        
        return '\n'.join(caption_parts)
    
    def run_single_post(self):
        """Execute a single post cycle with enterprise features"""
        print(f"\n{'='*60}")
        print(f"🚀 Enterprise Post Cycle - {datetime.now()}")
        print(f"{'='*60}\n")
        
        # Pre-flight checks
        if not self.pre_flight_checks():
            print("❌ Pre-flight checks failed. Aborting.")
            return
        
        # Check rate limits
        rate_check = self.rate_limiter.check_rate_limit('facebook_api')
        if not rate_check['allowed']:
            print(f"⏳ Rate limited. Waiting {rate_check.get('wait_seconds', 60)} seconds...")
            time.sleep(rate_check.get('wait_seconds', 60))
        
        # Get images
        print("📥 Fetching images from archives...")
        num_images = random.randint(1, self.max_images_per_post)
        
        if self.use_pro:
            images = self.scraper.smart_image_selection(
                self.sources, 
                count=num_images,
                max_pages_per_source=self.max_pages_per_source
            )
        else:
            images = self.scraper.get_random_images(self.sources, count=num_images)
        
        if not images:
            print("❌ No images found. Skipping this cycle.")
            return
        
        print(f"✅ Found {len(images)} image(s)")
        
        # Content filtering with strict NSFW detection
        print("🔍 Running strict NSFW detection and content safety checks...")
        safe_images = []
        for img in images:
            if self.use_pro and img.get('local_path'):
                # Run strict NSFW detection
                nsfw_result = self.nsfw_detector.detect_nsfw(img)
                
                # Check Facebook policy compliance
                compliance_result = self.facebook_compliance.check_compliance(img)
                
                if nsfw_result['blocked'] or not compliance_result['compliant']:
                    print(f"🚫 Image BLOCKED by NSFW filter: {img.get('url', 'unknown')}")
                    print(f"   Reason: {nsfw_result.get('reason', 'Unknown')}")
                    if compliance_result.get('violations'):
                        print(f"   Policy violations: {[v['policy'] for v in compliance_result['violations']]}")
                    
                    self.notifications.notify_content_flagged(
                        img.get('url', 'unknown'),
                        f"NSFW BLOCKED: {nsfw_result.get('reason', 'Unknown')}"
                    )
                else:
                    # Additional basic content filtering
                    filter_result = self.content_filter.comprehensive_check(img)
                    if filter_result['overall_safe']:
                        safe_images.append(img)
                        print(f"✅ Image passed safety checks: {img.get('url', 'unknown')}")
                    else:
                        print(f"⚠️  Image filtered by basic filter: {img.get('url', 'unknown')}")
            else:
                # For basic scraper, only run basic filtering
                filter_result = self.content_filter.comprehensive_check(img)
                if filter_result['overall_safe']:
                    safe_images.append(img)
        
        if not safe_images:
            print("❌ No safe images after filtering. Skipping this cycle.")
            return
        
        images = safe_images
        
        # Download images if using basic scraper
        downloaded_paths = []
        posted_urls = []
        
        if self.use_pro:
            downloaded_paths = [img['local_path'] for img in images if img.get('local_path')]
            posted_urls = [img['url'] for img in images]
            
            print(f"Selected {len(images)} high-quality images")
            for img in images:
                quality = img.get('quality', {})
                print(f"  - Score: {quality.get('quality_score', 0):.1f}/100, "
                      f"Size: {quality.get('width', 0)}x{quality.get('height', 0)}")
        else:
            for img in images:
                print(f"Downloading: {img['url']}")
                path, filename = self.scraper.download_image(img['url'])
                if path:
                    downloaded_paths.append(path)
                    posted_urls.append(img['url'])
                    print(f"Downloaded: {filename}")
        
        if not downloaded_paths:
            print("❌ Failed to download any images. Skipping this cycle.")
            return
        
        # Generate AI content
        print("\n🤖 Generating description and hashtags...")
        image_context = f"Source: {images[0]['source']}, Title: {images[0].get('title', '')}, Alt: {images[0].get('alt_text', '')}"
        ai_content = self.openrouter.generate_description(image_context)
        print(f"Generated: {ai_content['title']}")
        
        # Create caption
        caption = self.generate_caption(images[0], ai_content)
        print(f"\nCaption preview:\n{caption[:200]}...")
        
        # Post to Facebook
        print("\n📤 Posting to Facebook...")
        
        # Check rate limit before posting
        rate_check = self.rate_limiter.check_rate_limit('facebook_api')
        if not rate_check['allowed']:
            print(f"⏳ Rate limited. Waiting {rate_check.get('wait_seconds', 60)} seconds...")
            time.sleep(rate_check.get('wait_seconds', 60))
        
        try:
            if len(downloaded_paths) == 1:
                result = self.facebook.post_image(downloaded_paths[0], caption)
            else:
                result = self.facebook.post_multiple_images(downloaded_paths, caption)
            
            # Record rate limit usage
            self.rate_limiter.record_request('facebook_api', success='error' not in result)
            
            if 'error' not in result:
                print("✅ Post successful!")
                post_id = result.get('id', str(int(time.time())))
                
                # Mark as posted
                if self.use_pro:
                    self.scraper.mark_as_posted(posted_urls)
                
                # Track in analytics
                self.analytics.track_post({
                    'post_id': post_id,
                    'platform': 'facebook',
                    'image_url': images[0].get('url'),
                    'caption': caption,
                    'posted_at': datetime.now(),
                    'source': images[0].get('source'),
                    'category': images[0].get('category'),
                    'quality_score': images[0].get('quality', {}).get('quality_score', 0)
                })
                
                # Record in scheduler
                self.scheduler.record_post('facebook', datetime.now())
                
                # Send success notification
                self.notifications.notify_success(post_id)
                
                # Clear rate limit backoff on success
                self.rate_limiter.clear_backoff('facebook_api')
                
            else:
                print("❌ Post failed!")
                self.notifications.notify_failure(str(result.get('error')), 'facebook')
                
                # Trigger backoff on failure
                self.rate_limiter.trigger_backoff('facebook_api')
                
        except Exception as e:
            print(f"❌ Exception during posting: {e}")
            self.notifications.notify_failure(str(e), 'facebook')
            self.rate_limiter.trigger_backoff('facebook_api')
        
        # Cleanup
        for path in downloaded_paths:
            try:
                os.remove(path)
                print(f"Cleaned up: {path}")
            except:
                pass
        
        if self.use_pro:
            self.scraper.cleanup_cache(max_age_hours=24)
        
        # Record metrics
        self.health_monitor.record_metric('post_duration', time.time())
        
        print(f"\n{'='*60}")
        print(f"✅ Cycle completed at {datetime.now()}")
        print(f"{'='*60}\n")
    
    def calculate_next_post_time(self) -> datetime:
        """Calculate optimal next post time using intelligent scheduler"""
        optimal_time = self.scheduler.get_next_optimal_time(
            platform='facebook',
            min_hours_from_now=self.min_interval,
            max_hours_from_now=self.max_interval
        )
        return optimal_time
    
    def run_continuous(self):
        """Run continuous automation with intelligent scheduling"""
        print("🚀 Starting Enterprise Continuous Automation...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                self.run_single_post()
                
                next_time = self.calculate_next_post_time()
                print(f"\n🕐 Next optimal post: {next_time}")
                print(f"⏱️  Waiting {int((next_time - datetime.now()).total_seconds() / 60)} minutes...\n")
                
                wait_seconds = (next_time - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                    
            except KeyboardInterrupt:
                print("\n\n🛑 Automation stopped by user.")
                break
            except Exception as e:
                print(f"\n❌ Error in automation loop: {e}")
                self.notifications.notify_failure(str(e), 'automation_loop')
                print("Retrying in 1 hour...")
                time.sleep(3600)
    
    def generate_weekly_report(self):
        """Generate and send weekly analytics report"""
        print("📊 Generating weekly analytics report...")
        report = self.analytics.generate_report()
        self.notifications.notify_analytics_report(report)
        
        # Learn from engagement data
        self.scheduler.learn_from_engagement()
        
        # Clean up old records
        self.health_monitor.cleanup_old_records(days=7)
        
        print("✅ Weekly report generated and sent")
        return report

def main():
    """Main entry point for enterprise automation"""
    automation = EnterpriseAutomation()
    
    # Test Facebook connection
    print("🔍 Testing Facebook API connection...")
    if not automation.facebook.test_connection():
        print("❌ Facebook connection failed. Please check your credentials.")
        return
    
    # Store initial token
    token = os.getenv('FACEBOOK_ACCESS_TOKEN')
    if token:
        automation.token_manager.store_token('facebook', 'access', token, expires_in_days=60)
    
    # Run mode
    if os.getenv('GITHUB_ACTIONS'):
        print("Running in GitHub Actions mode - single post")
        automation.run_single_post()
    else:
        # Run continuous with intelligent scheduling
        automation.run_continuous()

if __name__ == "__main__":
    main()
