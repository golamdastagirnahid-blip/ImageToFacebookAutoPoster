import os
import sys
import random
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv
from image_scraper import ImageScraper
from image_scraper_pro import ImageScraperPro
from openrouter_client import OpenRouterClient
from facebook_poster import FacebookPoster
from image_processor import ImageProcessor
from health_report import HealthReporter

# Optional NSFW detector
try:
    from nsfw_detector import StrictNSFWDetector, FacebookPolicyCompliance
    NSFW_AVAILABLE = True
except Exception as e:
    print(f"NSFW detector not available: {e}")
    NSFW_AVAILABLE = False

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
        # Image post-processor (FB-optimal sizing + watermark + enhancement)
        self.processor = ImageProcessor(
            enable_watermark=os.getenv('ENABLE_WATERMARK', 'true').lower() == 'true',
            watermark_text=os.getenv('WATERMARK_TEXT', 'Public Domain Archives'),
            enable_enhance=os.getenv('ENABLE_ENHANCE', 'true').lower() == 'true',
        )
        
        # NSFW & content safety
        self.nsfw_detector = StrictNSFWDetector() if NSFW_AVAILABLE else None
        self.fb_compliance = FacebookPolicyCompliance() if NSFW_AVAILABLE else None
        # Health reporter (logs every run, generates STATUS.md)
        self.health = HealthReporter()
        
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
        """Generate organized Facebook caption with rich historical metadata"""
        parts = []
        
        # Title with emoji
        if ai_content.get('title'):
            parts.append(f"📌 {ai_content['title']}")
            parts.append("")
        
        # AI-generated educational description
        if ai_content.get('description'):
            parts.append(ai_content['description'])
            parts.append("")
        
        # Historical Details section (organized metadata)
        details = []
        if image_info.get('creator'):
            details.append(f"🎨 Creator: {image_info['creator']}")
        if image_info.get('date'):
            details.append(f"📅 Date: {image_info['date']}")
        if image_info.get('publisher'):
            details.append(f"🏛️ Publisher: {image_info['publisher']}")
        if image_info.get('language'):
            lang = image_info['language']
            if isinstance(lang, list):
                lang = ', '.join(str(l) for l in lang)
            details.append(f"🗣️ Language: {lang}")
        
        # Subject/tag list
        subj = image_info.get('subject') or image_info.get('tags')
        if subj:
            if isinstance(subj, list):
                subj_str = ', '.join(str(s) for s in subj[:6])
            else:
                subj_str = str(subj)
            if subj_str:
                details.append(f"🏷️ Subjects: {subj_str}")
        
        if details:
            parts.append("📜 Historical Details")
            parts.append("─" * 20)
            parts.extend(details)
            parts.append("")
        
        # Hashtags
        if ai_content.get('hashtags'):
            parts.append(ai_content['hashtags'])
            parts.append("")
        
        # Source credit
        credit = self.credit_template.format(source=image_info.get('source', 'Unknown'))
        parts.append(f"📚 {credit}")
        if image_info.get('parent_link'):
            parts.append(f"🔗 View original: {image_info['parent_link']}")
        
        # Disclaimer
        parts.append("")
        parts.append(f"ℹ️ {self.disclaimer_template}")
        
        return '\n'.join(parts)
    
    def run_single_post(self):
        """Execute a single post cycle"""
        print(f"\n{'='*50}")
        print(f"Starting post cycle at {datetime.now()}")
        print(f"{'='*50}\n")
        
        # Get images using appropriate scraper
        print("Fetching images from archives...")
        num_images = random.randint(1, self.max_images_per_post)
        
        # Source rotation: prioritize sources with FEWEST posts so far (fair coverage)
        # Falls back to random shuffle if pro scraper unavailable
        if self.is_pro:
            try:
                src_counts = self.scraper.get_source_post_counts()
                # Build (count, jitter, source) tuples for stable but varied ordering
                weighted = []
                for src in self.sources:
                    src_name = self.scraper.get_archive_name(src) if hasattr(self.scraper, 'get_archive_name') else src
                    count = src_counts.get(src_name, 0)
                    weighted.append((count, random.random(), src))
                weighted.sort()  # Lowest count first; jitter breaks ties
                shuffled_sources = [s for _, _, s in weighted]
                print(f"Source rotation (post counts): {[(c, s.split('/')[-1][:25]) for c, _, s in weighted]}")
            except Exception as e:
                print(f"Source rotation failed, using random: {e}")
                shuffled_sources = self.sources.copy()
                random.shuffle(shuffled_sources)
        else:
            shuffled_sources = self.sources.copy()
            random.shuffle(shuffled_sources)
        
        print(f"Source order this run: {[s.split('/')[-1][:30] for s in shuffled_sources]}")
        
        if self.is_pro:
            # Request more candidates so we have fallbacks if NSFW blocks the top pick
            images = self.scraper.smart_image_selection(
                shuffled_sources,
                count=10,  # Top 10 candidates - we'll iterate until one passes safety
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
        
        # Try each candidate in order until one passes safety checks
        chosen_idx = None
        for idx in range(len(images)):
            candidate = images[idx]
            cand_path = candidate.get('local_path')
            if not cand_path or not os.path.exists(cand_path):
                continue
            
            print(f"\n--- Evaluating candidate {idx+1}/{len(images)} ---")
            print(f"Title: {candidate.get('title', 'unknown')[:80]}")
            
            # Fetch full metadata + high-res image (archive.org items only)
            cand_url = candidate.get('url', '')
            cand_source = candidate.get('source', '')
            is_archive_org = 'archive.org' in cand_url or 'Internet Archive' in cand_source or 'David Rumsey' in cand_source or 'Cleveland' in cand_source or 'Propix' in cand_source or 'Metropolitan Museum of Art (Archive' in cand_source
            
            if self.is_pro and candidate.get('identifier') and is_archive_org:
                print("📚 Fetching full metadata from archive.org...")
                full_meta = self.scraper.fetch_full_metadata(candidate['identifier'])
                if full_meta.get('metadata'):
                    meta = full_meta['metadata']
                    for key in ['description', 'creator', 'date', 'subject', 'publisher',
                                'language', 'source', 'rights', 'coverage', 'contributor',
                                'notes', 'references', 'uploader']:
                        if meta.get(key) and not candidate.get(key):
                            candidate[key] = meta[key]
                    if meta.get('description'):
                        candidate['description'] = meta['description']
                    print(f"✅ Retrieved extended metadata ({len(meta)} fields)")
                
                # CRITICAL: Replace thumbnail with high-res image
                full_url = full_meta.get('full_image_url')
                if full_url:
                    print(f"🎨 Found high-res image: {full_url}")
                    # Download high-res version
                    hires_result = self.scraper.download_and_validate_image(full_url)
                    hires_path = hires_result.get('local_path') if hires_result else None
                    if hires_path and os.path.exists(hires_path):
                        # Verify resolution is acceptable for Facebook
                        try:
                            from PIL import Image as PILImage
                            with PILImage.open(hires_path) as im:
                                w, h = im.size
                                print(f"   High-res dimensions: {w}x{h}")
                                if w >= 600 and h >= 400:
                                    # Replace thumbnail with hires
                                    try:
                                        os.remove(cand_path)
                                    except Exception:
                                        pass
                                    candidate['local_path'] = hires_path
                                    candidate['url'] = full_url
                                    candidate['width'] = w
                                    candidate['height'] = h
                                    cand_path = hires_path
                                    print(f"✅ Using high-res version for posting")
                                else:
                                    print(f"⚠️  High-res too small ({w}x{h}) - skipping candidate")
                                    try:
                                        os.remove(hires_path)
                                        os.remove(cand_path)
                                    except Exception:
                                        pass
                                    if self.is_pro:
                                        self.scraper.mark_as_posted([candidate['url']])
                                    continue
                        except Exception as e:
                            print(f"   Resolution check failed: {e}")
                else:
                    # No full-res URL found - thumbnail will be too small for FB
                    print(f"⚠️  No high-res available, thumbnail only - skipping")
                    try:
                        os.remove(cand_path)
                    except Exception:
                        pass
                    if self.is_pro:
                        self.scraper.mark_as_posted([candidate['url']])
                    continue
            else:
                # Non-archive.org source: verify the already-downloaded image is FB-quality
                # Try to upgrade to full_image_url if different from current url
                full_url = candidate.get('full_image_url')
                if full_url and full_url != candidate.get('url'):
                    print(f"🎨 Trying full-res from {cand_source}: {full_url}")
                    try:
                        hires_result = self.scraper.download_and_validate_image(full_url)
                        if hires_result and hires_result.get('local_path'):
                            try:
                                os.remove(cand_path)
                            except Exception:
                                pass
                            cand_path = hires_result['local_path']
                            candidate['local_path'] = cand_path
                    except Exception as e:
                        print(f"   Full-res download failed (using thumb): {e}")
                
                # Verify dimensions
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(cand_path) as im:
                        w, h = im.size
                        print(f"   Dimensions: {w}x{h}")
                        if w < 500 or h < 350:
                            print(f"⚠️  Too small for FB - skipping")
                            try:
                                os.remove(cand_path)
                            except Exception:
                                pass
                            if self.is_pro:
                                self.scraper.mark_as_posted([candidate['url']])
                            continue
                        candidate['width'] = w
                        candidate['height'] = h
                except Exception as e:
                    print(f"   Dimension check failed: {e}")
            
            # NSFW check
            if self.nsfw_detector:
                print("🔒 Running NSFW safety check...")
                try:
                    nsfw_info = dict(candidate)
                    nsfw_info['local_path'] = cand_path
                    nsfw_result = self.nsfw_detector.detect_nsfw(nsfw_info)
                    if nsfw_result.get('blocked') or nsfw_result.get('overall_level') in ('high_risk', 'blocked'):
                        print(f"⛔ Blocked: {nsfw_result.get('reason', 'unknown')}")
                        text_check = nsfw_result.get('checks', {}).get('text', {})
                        if text_check.get('keywords'):
                            print(f"   Triggered: {text_check['keywords']}")
                        # Mark this candidate as posted to avoid re-evaluating
                        if self.is_pro:
                            self.scraper.mark_as_posted([candidate['url']])
                        # Cleanup this image and try next
                        try:
                            os.remove(cand_path)
                        except Exception:
                            pass
                        continue
                    print(f"✅ NSFW check passed (level: {nsfw_result.get('overall_level', 'safe')})")
                except Exception as e:
                    print(f"NSFW check error (continuing with this candidate): {e}")
            
            # This candidate passed!
            chosen_idx = idx
            break
        
        if chosen_idx is None:
            print("\n❌ No candidates passed safety checks. Skipping this cycle.")
            for p in downloaded_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass
            return
        
        # Reorder so chosen candidate is first
        images[0], images[chosen_idx] = images[chosen_idx], images[0]
        downloaded_paths[0] = images[0]['local_path']
        posted_urls[0] = images[0]['url']
        print(f"\n✅ Selected candidate #{chosen_idx+1} for posting")
        
        # Generate AI content for the first image using FULL metadata
        print("\nGenerating description and hashtags...")
        img = images[0]
        # Build rich metadata context for AI
        meta_lines = [f"Archive Source: {img.get('source', 'Unknown')}"]
        if img.get('title'):
            meta_lines.append(f"Title: {img['title']}")
        if img.get('creator'):
            meta_lines.append(f"Creator/Artist: {img['creator']}")
        if img.get('date'):
            meta_lines.append(f"Date: {img['date']}")
        if img.get('publisher'):
            meta_lines.append(f"Publisher: {img['publisher']}")
        if img.get('language'):
            meta_lines.append(f"Language: {img['language']}")
        if img.get('subject') or img.get('tags'):
            tags = img.get('subject') or img.get('tags') or []
            if isinstance(tags, list):
                tags_str = ', '.join(str(t) for t in tags[:10])
            else:
                tags_str = str(tags)
            if tags_str:
                meta_lines.append(f"Subject Tags: {tags_str}")
        if img.get('description'):
            meta_lines.append(f"Description: {img['description'][:500]}")
        if img.get('alt_text') and img.get('alt_text') != img.get('description'):
            meta_lines.append(f"Alt Text: {img['alt_text'][:200]}")
        if img.get('parent_link'):
            meta_lines.append(f"Source Link: {img['parent_link']}")
        
        image_context = '\n'.join(meta_lines)
        print(f"Metadata being sent to AI:\n{image_context}\n")
        ai_content = self.openrouter.generate_description(image_context)
        print(f"Generated: {ai_content['title']}")
        
        # Create caption
        caption = self.generate_caption(images[0], ai_content)
        print(f"\nCaption preview:\n{caption[:200]}...")
        
        # Post-process the image for Facebook (resize, watermark, enhance, optimize)
        print("\n🎨 Post-processing image for Facebook...")
        try:
            source_credit = images[0].get('source', 'Public Domain Archives')
            self.processor.watermark_text = source_credit
            processed_path = self.processor.process(downloaded_paths[0], source_name=source_credit)
            downloaded_paths[0] = processed_path
        except Exception as e:
            print(f"   Processing failed (using original): {e}")
        
        # Post to Facebook (use single image for reliability)
        print("\nPosting to Facebook...")
        # Use the LOCAL processed file (not URL) so watermark/enhancements are preserved
        first_image_url = None  # Force file upload of processed image
        
        # Pre-mark as posted BEFORE FB call - prevents reposts even if response parsing fails
        # If FB actually fails, we accept losing this one item (50,000+ available)
        if self.is_pro:
            self.scraper.mark_as_posted(posted_urls[:1])
            # Also store identifier for stronger dedup
            ident = images[0].get('identifier')
            if ident:
                print(f"   Reserved identifier: {ident}")
        
        result = self.facebook.post_image(downloaded_paths[0], caption, image_url=first_image_url)
        
        if 'error' not in result:
            print("✅ Post successful!")
            try:
                self.health.log_run('success', {
                    'title': ai_content.get('title', 'unknown'),
                    'source': images[0].get('source', 'unknown'),
                    'image_size': f"{images[0].get('width', 0)}x{images[0].get('height', 0)}",
                    'post_id': result.get('post_id') or result.get('id', 'unknown'),
                    'identifier': images[0].get('identifier', ''),
                })
                self.health.generate_status_md()
            except Exception as e:
                print(f"Health log error: {e}")
        else:
            print("❌ Post failed - but image is marked as attempted to prevent retry loop")
            try:
                self.health.log_run('failure', {
                    'error': str(result.get('error', 'unknown'))[:200],
                    'stage': 'facebook_post',
                    'title': ai_content.get('title', 'unknown'),
                })
                self.health.generate_status_md()
            except Exception:
                pass
        
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
    """Main entry point with self-healing retry logic"""
    import traceback
    
    max_attempts = 3
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"\n{'='*60}")
            print(f"🤖 Automation attempt {attempt}/{max_attempts}")
            print(f"{'='*60}\n")
            
            # Self-heal: ensure cache directory exists
            os.makedirs('image_cache', exist_ok=True)
            
            automation = ImageAutomation()
            
            # Test Facebook connection (retry on transient failure)
            print("Testing Facebook API connection...")
            fb_ok = False
            for fb_attempt in range(3):
                try:
                    if automation.facebook.test_connection():
                        fb_ok = True
                        break
                    print(f"  Facebook test failed, retrying in 5s... ({fb_attempt+1}/3)")
                    time.sleep(5)
                except Exception as e:
                    print(f"  Facebook test exception: {e}")
                    time.sleep(5)
            
            if not fb_ok:
                print("❌ Facebook connection failed after 3 attempts.")
                if attempt < max_attempts:
                    print(f"Will retry full cycle in 30s...")
                    time.sleep(30)
                    continue
                return
            
            # Execute the cycle
            if os.getenv('GITHUB_ACTIONS'):
                print("Running in GitHub Actions mode - single post")
                automation.run_single_post()
            else:
                automation.run_continuous()
            
            # Success - exit
            print("\n✅ Automation completed successfully")
            return
            
        except KeyboardInterrupt:
            print("\n\nAutomation stopped by user.")
            return
        except Exception as e:
            last_exception = e
            print(f"\n❌ Attempt {attempt} failed: {type(e).__name__}: {e}")
            traceback.print_exc()
            if attempt < max_attempts:
                wait = 30 * attempt  # Backoff: 30s, 60s, 90s
                print(f"\n🔄 Self-recovery: waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                print(f"\n💀 All {max_attempts} attempts exhausted. Final error:")
                traceback.print_exc()
                # Exit with non-zero so GitHub Actions marks as failed
                sys.exit(1)

if __name__ == "__main__":
    import sys
    main()
