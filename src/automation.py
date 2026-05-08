import os
import random
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from image_scraper import ImageScraper
from image_scraper_pro import ImageScraperPro
from openrouter_client import OpenRouterClient
from facebook_poster import FacebookPoster

load_dotenv()

class ImageAutomation:
    def __init__(self, use_pro: bool = True):
        # Use pro scraper by default for better quality
        if use_pro and os.getenv('USE_PRO_SCRAPER', 'true').lower() == 'true':
            print("🚀 Using PRO image scraper with AI-powered selection")
            self.scraper = ImageScraperPro()
        else:
            print("Using basic image scraper")
            self.scraper = ImageScraper()
            
        self.openrouter = OpenRouterClient()
        self.facebook = FacebookPoster()
        
        # Configuration
        self.min_interval = int(os.getenv('MIN_POST_INTERVAL_HOURS', '4') or '4')
        self.max_interval = int(os.getenv('MAX_POST_INTERVAL_HOURS', '12') or '12')
        self.max_images_per_post = int(os.getenv('MAX_IMAGES_PER_POST', '3') or '3')
        self.sources = [s.strip() for s in os.getenv('ARCHIVE_SOURCES', '').split(',') if s.strip()]
        self.credit_template = os.getenv('CREDIT_TEXT', 'Image Source: {source}') or 'Image Source: {source}'
        self.disclaimer_template = os.getenv('DISCLAIMER_TEXT', 'Disclaimer: This image is used for commercial purposes under public domain or Creative Commons license.') or 'Disclaimer: This image is used for commercial purposes under public domain or Creative Commons license.'
        
        # Pro scraper settings
        self.max_pages_per_source = int(os.getenv('MAX_PAGES_PER_SOURCE', '5') or '5')
        self.is_pro = use_pro and os.getenv('USE_PRO_SCRAPER', 'true').lower() == 'true'
        
    def generate_caption(self, image_info: dict, ai_content: dict) -> str:
        """Generate full caption with description, hashtags, credits, and disclaimer"""
        caption_parts = []
        
        # Add title if available
        if ai_content.get('title'):
            caption_parts.append(f"📌 {ai_content['title']}\n")
        
        # Add AI-generated description
        if ai_content.get('description'):
            caption_parts.append(f"{ai_content['description']}\n")
        
        # Add hashtags
        if ai_content.get('hashtags'):
            caption_parts.append(f"\n{ai_content['hashtags']}")
        
        # Add credits
        credit = self.credit_template.format(source=image_info.get('source', 'Unknown'))
        caption_parts.append(f"\n\n{credit}")
        
        # Add disclaimer
        caption_parts.append(f"\n{self.disclaimer_template}")
        
        return '\n'.join(caption_parts)
    
    def run_single_post(self):
        """Execute a single post cycle"""
        print(f"\n{'='*50}")
        print(f"Starting post cycle at {datetime.now()}")
        print(f"{'='*50}\n")
        
        # Get images using appropriate scraper
        print("Fetching images from archives...")
        num_images = random.randint(1, self.max_images_per_post)
        
        if self.is_pro:
            # Use pro scraper with smart selection
            images = self.scraper.smart_image_selection(
                self.sources, 
                count=num_images,
                max_pages_per_source=self.max_pages_per_source
            )
            
            if not images:
                print("No quality images found. Skipping this cycle.")
                return
            
            # Pro scraper already downloads and validates
            downloaded_paths = [img['local_path'] for img in images if img.get('local_path')]
            posted_urls = [img['url'] for img in images]
            
            print(f"Selected {len(images)} high-quality images")
            for img in images:
                quality = img.get('quality', {})
                print(f"  - Score: {quality.get('quality_score', 0):.1f}/100, "
                      f"Size: {quality.get('width', 0)}x{quality.get('height', 0)}")
        else:
            # Use basic scraper
            images = self.scraper.get_random_images(self.sources, count=num_images)
            
            if not images:
                print("No images found. Skipping this cycle.")
                return
            
            print(f"Found {len(images)} image(s)")
            
            # Download images
            downloaded_paths = []
            for img in images:
                print(f"Downloading: {img['url']}")
                path, filename = self.scraper.download_image(img['url'])
                if path:
                    downloaded_paths.append(path)
                    print(f"Downloaded: {filename}")
            posted_urls = [img['url'] for img in images]
        
        if not downloaded_paths:
            print("Failed to download any images. Skipping this cycle.")
            return
        
        # Generate AI content for the first image
        print("\nGenerating description and hashtags...")
        image_context = f"Source: {images[0]['source']}, Title: {images[0].get('title', '')}, Alt: {images[0].get('alt_text', '')}"
        ai_content = self.openrouter.generate_description(image_context)
        print(f"Generated: {ai_content['title']}")
        
        # Create caption
        caption = self.generate_caption(images[0], ai_content)
        print(f"\nCaption preview:\n{caption[:200]}...")
        
        # Post to Facebook (use single image for reliability)
        print("\nPosting to Facebook...")
        # Post first image with caption (most reliable approach)
        result = self.facebook.post_image(downloaded_paths[0], caption)
        
        if 'error' not in result:
            print("✅ Post successful!")
            # Mark as posted in database if using pro scraper
            if self.is_pro:
                self.scraper.mark_as_posted(posted_urls[:1])
        else:
            print("❌ Post failed!")
        
        # Cleanup downloaded images
        for path in downloaded_paths:
            try:
                os.remove(path)
                print(f"Cleaned up: {path}")
            except:
                pass
        
        # Cleanup cache if using pro scraper
        if self.is_pro:
            self.scraper.cleanup_cache(max_age_hours=24)
        
        print(f"\n{'='*50}")
        print(f"Cycle completed at {datetime.now()}")
        print(f"{'='*50}\n")
    
    def calculate_next_post_time(self) -> datetime:
        """Calculate random time for next post"""
        hours = random.uniform(self.min_interval, self.max_interval)
        next_time = datetime.now() + timedelta(hours=hours)
        return next_time
    
    def run_continuous(self):
        """Run continuous automation with randomized intervals"""
        print("Starting continuous automation mode...")
        print("Press Ctrl+C to stop\n")
        
        while True:
            try:
                # Run post
                self.run_single_post()
                
                # Calculate next post time
                next_time = self.calculate_next_post_time()
                print(f"\n🕐 Next post scheduled for: {next_time}")
                print(f"⏱️  Waiting {int((next_time - datetime.now()).total_seconds() / 60)} minutes...\n")
                
                # Wait until next post time
                wait_seconds = (next_time - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
                    
            except KeyboardInterrupt:
                print("\n\nAutomation stopped by user.")
                break
            except Exception as e:
                print(f"\nError in automation loop: {e}")
                print("Retrying in 1 hour...")
                time.sleep(3600)

def main():
    """Main entry point"""
    automation = ImageAutomation()
    
    # Test Facebook connection first
    print("Testing Facebook API connection...")
    if not automation.facebook.test_connection():
        print("❌ Facebook connection failed. Please check your credentials.")
        return
    
    # Run single post for GitHub Actions
    if os.getenv('GITHUB_ACTIONS'):
        print("Running in GitHub Actions mode - single post")
        automation.run_single_post()
    else:
        # Run continuous mode locally
        automation.run_continuous()

if __name__ == "__main__":
    main()
