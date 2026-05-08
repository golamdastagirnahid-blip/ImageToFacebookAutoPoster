import requests
from bs4 import BeautifulSoup
import random
import time
from urllib.parse import urljoin, urlparse
import os
from typing import List, Dict, Tuple, Optional, Set
import re
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from io import BytesIO
import sqlite3
from datetime import datetime, timedelta

class ImageScraperPro:
    """Professional-grade image scraper with AI-powered selection"""
    
    def __init__(self, cache_dir: str = 'image_cache', db_path: str = 'image_database.db'):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.db_path = db_path
        self._init_database()
        
        # Quality thresholds
        self.min_width = 800
        self.min_height = 600
        self.min_file_size = 50 * 1024  # 50KB
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
        # Duplicate detection
        self.posted_urls: Set[str] = self._load_posted_urls()
        
        # Performance settings
        self.max_workers = 5
        self.request_timeout = 30
        self.max_retries = 3
        self.retry_delay = 2
        
    def _init_database(self):
        """Initialize SQLite database for caching and tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                url TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                alt_text TEXT,
                width INTEGER,
                height INTEGER,
                file_size INTEGER,
                quality_score REAL,
                scraped_at TIMESTAMP,
                last_posted TIMESTAMP,
                post_count INTEGER DEFAULT 0,
                content_hash TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS failed_urls (
                url TEXT PRIMARY KEY,
                error TEXT,
                failed_at TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_posted_urls(self) -> Set[str]:
        """Load set of already posted URLs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT url FROM images WHERE post_count > 0')
        posted = {row[0] for row in cursor.fetchall()}
        conn.close()
        return posted
    
    def _is_duplicate(self, url: str) -> bool:
        """Check if image was already posted"""
        return url in self.posted_urls
    
    def _calculate_content_hash(self, image_data: bytes) -> str:
        """Calculate hash of image content for duplicate detection"""
        return hashlib.md5(image_data).hexdigest()
    
    def _validate_image_url(self, url: str) -> bool:
        """Validate image URL before download"""
        if not url or url.startswith('data:'):
            return False
        
        # Check for valid extensions
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
        return any(url.lower().endswith(ext) for ext in valid_extensions)
    
    def _check_image_quality(self, image_data: bytes) -> Dict:
        """Analyze image quality and return metrics"""
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            file_size = len(image_data)
            
            # Calculate quality score (0-100)
            score = 0
            
            # Resolution score (40 points)
            resolution_score = min(40, (width * height) / (1920 * 1080) * 40)
            score += resolution_score
            
            # Aspect ratio score (20 points) - prefer 3:2 to 16:9
            aspect_ratio = width / height
            if 1.3 <= aspect_ratio <= 1.8:
                score += 20
            elif 1.0 <= aspect_ratio <= 2.0:
                score += 10
            
            # File size score (20 points) - prefer reasonable sizes
            if self.min_file_size <= file_size <= 2 * 1024 * 1024:
                score += 20
            elif file_size > self.min_file_size:
                score += 10
            
            # Format score (20 points) - prefer JPEG/PNG
            if img.format in ['JPEG', 'PNG']:
                score += 20
            elif img.format:
                score += 10
            
            return {
                'width': width,
                'height': height,
                'file_size': file_size,
                'format': img.format,
                'quality_score': min(100, score),
                'valid': (width >= self.min_width and 
                         height >= self.min_height and
                         self.min_file_size <= file_size <= self.max_file_size)
            }
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def _fetch_with_retry(self, url: str) -> Optional[requests.Response]:
        """Fetch URL with retry logic"""
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(url, timeout=self.request_timeout)
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    print(f"Failed to fetch {url} after {self.max_retries} attempts: {e}")
                    return None
    
    def scrape_archive_org_paginated(self, base_url: str, max_pages: int = 10, max_images: int = 100) -> List[Dict]:
        """Scrape multiple pages from archive.org"""
        all_images = []
        
        for page in range(1, max_pages + 1):
            page_url = f"{base_url}&page={page}" if '?' in base_url else f"{base_url}?page={page}"
            
            print(f"Scraping page {page}/{max_pages}: {page_url}")
            images = self._scrape_archive_page(page_url)
            
            if not images:
                print(f"No images found on page {page}, stopping pagination")
                break
            
            all_images.extend(images)
            
            if len(all_images) >= max_images:
                break
            
            # Human-like delay between pages
            time.sleep(random.uniform(2, 5))
        
        return all_images[:max_images]
    
    def _scrape_archive_page(self, url: str) -> List[Dict]:
        """Scrape single archive.org page"""
        images = []
        
        try:
            response = self._fetch_with_retry(url)
            if not response:
                return images
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all image elements
            img_tags = soup.find_all('img')
            
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and self._validate_image_url(src):
                    full_url = urljoin(url, src)
                    
                    # Skip if already posted
                    if self._is_duplicate(full_url):
                        continue
                    
                    image_info = {
                        'url': full_url,
                        'source': self._get_archive_name(url),
                        'alt_text': img.get('alt', ''),
                        'title': soup.find('title').text if soup.find('title') else '',
                        'parent_link': self._find_parent_link(img, url)
                    }
                    images.append(image_info)
                    
        except Exception as e:
            print(f"Error scraping {url}: {e}")
        
        return images
    
    def _find_parent_link(self, img_tag, base_url: str) -> str:
        """Find the parent link (image detail page) for archive items"""
        parent = img_tag.find_parent('a')
        if parent and parent.get('href'):
            return urljoin(base_url, parent.get('href'))
        return ''
    
    def download_and_validate_image(self, url: str) -> Optional[Dict]:
        """Download image and validate quality"""
        try:
            response = self._fetch_with_retry(url)
            if not response:
                return None
            
            image_data = response.content
            
            # Check file size
            if len(image_data) < self.min_file_size:
                return None
            
            # Analyze quality
            quality = self._check_image_quality(image_data)
            
            if not quality.get('valid'):
                return None
            
            # Calculate content hash
            content_hash = self._calculate_content_hash(image_data)
            
            # Save to cache
            filename = f"{content_hash[:16]}_{int(time.time())}.jpg"
            cache_path = os.path.join(self.cache_dir, filename)
            
            with open(cache_path, 'wb') as f:
                f.write(image_data)
            
            return {
                'url': url,
                'local_path': cache_path,
                'filename': filename,
                'quality': quality,
                'content_hash': content_hash
            }
            
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return None
    
    def process_images_parallel(self, image_urls: List[Dict], max_workers: int = None) -> List[Dict]:
        """Download and validate images in parallel"""
        if max_workers is None:
            max_workers = self.max_workers
        
        valid_images = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(self.download_and_validate_image, img['url']): img 
                for img in image_urls
            }
            
            for future in as_completed(future_to_url):
                original_info = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        # Merge original info with validation result
                        result.update(original_info)
                        valid_images.append(result)
                except Exception as e:
                    print(f"Error processing {original_info['url']}: {e}")
        
        return valid_images
    
    def rank_images(self, images: List[Dict]) -> List[Dict]:
        """Rank images by quality score and other factors"""
        for img in images:
            score = img.get('quality', {}).get('quality_score', 50)
            
            # Boost score for images with good metadata
            if img.get('alt_text') and len(img.get('alt_text', '')) > 10:
                score += 10
            
            if img.get('title') and len(img.get('title', '')) > 10:
                score += 10
            
            # Boost for certain sources
            if 'Metropolitan' in img.get('source', ''):
                score += 5
            
            img['final_score'] = score
        
        # Sort by score descending
        return sorted(images, key=lambda x: x.get('final_score', 0), reverse=True)
    
    def select_best_images(self, images: List[Dict], count: int = 3) -> List[Dict]:
        """Select best images from ranked list"""
        ranked = self.rank_images(images)
        return ranked[:count]
    
    def save_to_database(self, images: List[Dict]):
        """Save image metadata to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for img in images:
            cursor.execute('''
                INSERT OR REPLACE INTO images 
                (url, source, title, alt_text, width, height, file_size, quality_score, scraped_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                img['url'],
                img.get('source', ''),
                img.get('title', ''),
                img.get('alt_text', ''),
                img.get('quality', {}).get('width', 0),
                img.get('quality', {}).get('height', 0),
                img.get('quality', {}).get('file_size', 0),
                img.get('quality', {}).get('quality_score', 0),
                datetime.now(),
                img.get('content_hash', '')
            ))
        
        conn.commit()
        conn.close()
    
    def mark_as_posted(self, urls: List[str]):
        """Mark images as posted in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for url in urls:
            cursor.execute('''
                UPDATE images 
                SET last_posted = ?, post_count = post_count + 1
                WHERE url = ?
            ''', (datetime.now(), url))
            self.posted_urls.add(url)
        
        conn.commit()
        conn.close()
    
    def get_archive_name(self, url: str) -> str:
        """Extract archive name from URL"""
        if 'david-rumsey' in url:
            return 'David Rumsey Map Collection'
        elif 'metropolitanmuseum' in url:
            return 'Metropolitan Museum of Art'
        elif 'propix' in url:
            return 'Propix Archive'
        elif 'clevelandart' in url:
            return 'Cleveland Museum of Art'
        else:
            return 'Internet Archive'
    
    def smart_image_selection(self, sources: List[str], count: int = 3, max_pages_per_source: int = 5) -> List[Dict]:
        """Intelligent image selection with pagination, quality filtering, and ranking"""
        all_candidates = []
        
        for source in sources:
            print(f"\nProcessing source: {source}")
            
            if 'archive.org' in source:
                # Paginated scraping
                images = self.scrape_archive_org_paginated(source, max_pages=max_pages_per_source, max_images=50)
            elif 'publicdomainreview.org' in source:
                images = self._scrape_archive_page(source)
            else:
                continue
            
            print(f"Found {len(images)} candidate images")
            
            # Download and validate in parallel
            valid_images = self.process_images_parallel(images, max_workers=3)
            print(f"Validated {len(valid_images)} images")
            
            all_candidates.extend(valid_images)
            
            # Delay between sources
            time.sleep(random.uniform(3, 6))
        
        print(f"\nTotal candidates: {len(all_candidates)}")
        
        # Select best images
        best_images = self.select_best_images(all_candidates, count=count)
        print(f"Selected {len(best_images)} best images")
        
        # Save to database
        self.save_to_database(best_images)
        
        return best_images
    
    def cleanup_cache(self, max_age_hours: int = 24):
        """Clean up old cached images"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for filename in os.listdir(self.cache_dir):
            filepath = os.path.join(self.cache_dir, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            if file_time < cutoff:
                try:
                    os.remove(filepath)
                    print(f"Cleaned up: {filename}")
                except:
                    pass
