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
        
        # Quality thresholds (read from environment variables)
        self.min_width = int(os.getenv('MIN_IMAGE_WIDTH', '100') or '100')
        self.min_height = int(os.getenv('MIN_IMAGE_HEIGHT', '100') or '100')
        self.min_file_size = int(os.getenv('MIN_IMAGE_SIZE_KB', '1') or '1') * 1024
        self.max_file_size = int(os.getenv('MAX_IMAGE_SIZE_MB', '50') or '50') * 1024 * 1024
        
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
    
    def _is_duplicate(self, url: str, identifier: str = None, content_hash: str = None) -> bool:
        """Check if image was already posted using multiple signals"""
        # Layer 1: URL match
        if url in self.posted_urls:
            return True
        # Layer 2: Archive identifier match (catches same item at different URLs)
        if identifier:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM images WHERE url LIKE ? AND post_count > 0 LIMIT 1",
                    (f"%{identifier}%",)
                )
                if cursor.fetchone():
                    conn.close()
                    return True
                conn.close()
            except Exception:
                pass
        # Layer 3: Content hash match
        if content_hash:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM images WHERE content_hash = ? AND post_count > 0 LIMIT 1",
                    (content_hash,)
                )
                if cursor.fetchone():
                    conn.close()
                    return True
                conn.close()
            except Exception:
                pass
        return False
    
    def _calculate_content_hash(self, image_data: bytes) -> str:
        """Calculate hash of image content for duplicate detection"""
        return hashlib.md5(image_data).hexdigest()
    
    def _validate_image_url(self, url: str) -> bool:
        """Validate image URL"""
        if not url or url.startswith('data:'):
            return False
        return True
    
    def _get_archive_name(self, url: str) -> str:
        """Extract archive name from URL"""
        if 'david-rumsey' in url:
            return 'David Rumsey Map Collection'
        elif 'metropolitanmuseum' in url:
            return 'Metropolitan Museum of Art'
        elif 'propix' in url:
            return 'Propix Archive'
        elif 'clevelandart' in url:
            return 'Cleveland Museum of Art'
        elif 'publicdomainreview' in url:
            return 'The Public Domain Review'
        else:
            return 'Internet Archive'
    
    def _is_text_image(self, img: Image) -> bool:
        """Detect if image is primarily text (book pages, documents, etc.)
        Text images typically have:
        - Very low color variance (mostly black/white)
        - High contrast with sharp edges
        - Predominantly grayscale
        """
        try:
            # Resize for faster analysis
            small = img.copy()
            small.thumbnail((200, 200))
            
            # Convert to RGB if needed
            if small.mode != 'RGB':
                small = small.convert('RGB')
            
            # Sample pixels and analyze color distribution
            pixels = list(small.getdata())
            total = len(pixels)
            if total == 0:
                return False
            
            # Count "text-like" pixels: very dark or very light
            text_pixels = 0
            color_pixels = 0
            for r, g, b in pixels:
                avg = (r + g + b) / 3
                # Very dark or very light (text characteristic)
                if avg < 50 or avg > 220:
                    text_pixels += 1
                # Has significant color (non-grayscale)
                max_diff = max(abs(r-g), abs(g-b), abs(r-b))
                if max_diff > 30:
                    color_pixels += 1
            
            text_ratio = text_pixels / total
            color_ratio = color_pixels / total
            
            # Text image: high text-pixel ratio AND low color variation
            is_text = text_ratio > 0.75 and color_ratio < 0.10
            return is_text
            
        except Exception:
            return False
    
    def _check_image_quality(self, image_data: bytes) -> Dict:
        """Analyze image quality and return metrics"""
        try:
            img = Image.open(BytesIO(image_data))
            width, height = img.size
            file_size = len(image_data)
            
            # Filter out text-only images (book pages, documents)
            if self._is_text_image(img):
                return {'valid': False, 'reason': 'text_image', 'width': width, 'height': height}
            
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
        """Scrape thousands of images from archive.org using their official API"""
        all_images = []
        
        # Extract collection identifier from URL
        # e.g., https://archive.org/details/david-rumsey-map-collection?page=3 -> david-rumsey-map-collection
        collection = self._extract_collection_id(base_url)
        if not collection:
            print(f"Could not extract collection from: {base_url}")
            return []
        
        print(f"Using archive.org API for collection: {collection}")
        archive_name = self._get_archive_name(base_url)
        
        # First, get total item count so we can pick a random page range
        total_items = self._get_collection_size(collection)
        print(f"Collection has ~{total_items} total items")
        
        # Archive.org search API - returns up to 10,000 items per query
        rows_per_page = 100
        max_available_pages = max(1, min(100, total_items // rows_per_page))
        
        # Pick RANDOM starting page so we sample different items each run
        start_page = random.randint(1, max_available_pages) if max_available_pages > 1 else 1
        print(f"Starting from random page {start_page} of {max_available_pages}")
        
        for offset in range(max_pages):
            page = ((start_page - 1 + offset) % max_available_pages) + 1
            # Use random sort seed that changes each run
            random_seed = random.randint(1, 999999)
            search_url = (
                f"https://archive.org/advancedsearch.php"
                f"?q=collection%3A{collection}+AND+mediatype%3Aimage"
                f"&fl%5B%5D=identifier&fl%5B%5D=title&fl%5B%5D=description"
                f"&fl%5B%5D=creator&fl%5B%5D=date&fl%5B%5D=subject"
                f"&fl%5B%5D=publisher&fl%5B%5D=language"
                f"&sort%5B%5D=random+{random_seed}"
                f"&rows={rows_per_page}&page={page}&output=json"
            )
            
            print(f"Fetching page {page} (seed {random_seed}) from archive.org API")
            try:
                response = self._fetch_with_retry(search_url)
                if not response:
                    break
                
                data = response.json()
                docs = data.get('response', {}).get('docs', [])
                
                if not docs:
                    print(f"No more items on page {page}")
                    break
                
                for doc in docs:
                    identifier = doc.get('identifier')
                    if not identifier:
                        continue
                    
                    # Get the main image for this item
                    # Archive.org provides a thumbnail at: https://archive.org/services/img/<identifier>
                    # And full file via metadata API
                    item_image_url = self._get_archive_item_image(identifier)
                    if not item_image_url:
                        continue
                    
                    # Skip if duplicate (URL or identifier match)
                    if self._is_duplicate(item_image_url, identifier=identifier):
                        continue
                    
                    # Extract rich metadata
                    description = doc.get('description', '')
                    if isinstance(description, list):
                        description = ' '.join(description)
                    
                    creator = doc.get('creator', '')
                    if isinstance(creator, list):
                        creator = ', '.join(creator)
                    
                    subject = doc.get('subject', [])
                    if isinstance(subject, str):
                        subject = [subject]
                    
                    all_images.append({
                        'url': item_image_url,
                        'source': archive_name,
                        'alt_text': description[:300] if description else '',
                        'title': doc.get('title', identifier),
                        'description': description,
                        'creator': creator,
                        'date': doc.get('date', ''),
                        'subject': subject,
                        'tags': subject,
                        'publisher': doc.get('publisher', ''),
                        'language': doc.get('language', ''),
                        'parent_link': f"https://archive.org/details/{identifier}",
                        'identifier': identifier
                    })
                    
                    if len(all_images) >= max_images:
                        return all_images
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                print(f"Error fetching archive.org page {page}: {e}")
                break
        
        return all_images[:max_images]
    
    def _extract_collection_id(self, url: str) -> Optional[str]:
        """Extract collection identifier from archive.org URL"""
        try:
            # Match https://archive.org/details/<collection>?...
            match = re.search(r'archive\.org/details/([^/?&]+)', url)
            if match:
                return match.group(1)
        except:
            pass
        return None
    
    def _get_archive_item_image(self, identifier: str) -> Optional[str]:
        """Get main image URL for an archive.org item"""
        # Archive.org provides a service for item images
        # Use the high-quality thumbnail service which always works
        return f"https://archive.org/services/img/{identifier}"
    
    def _get_collection_size(self, collection: str) -> int:
        """Get approximate total item count in an archive.org collection"""
        try:
            url = (
                f"https://archive.org/advancedsearch.php"
                f"?q=collection%3A{collection}+AND+mediatype%3Aimage"
                f"&rows=0&output=json"
            )
            response = self._fetch_with_retry(url)
            if response:
                data = response.json()
                return int(data.get('response', {}).get('numFound', 100))
        except Exception as e:
            print(f"Could not get collection size: {e}")
        return 1000  # Default estimate
    
    def fetch_full_metadata(self, identifier: str) -> Dict:
        """Fetch FULL metadata for an archive.org item (much richer than search)"""
        try:
            url = f"https://archive.org/metadata/{identifier}"
            response = self._fetch_with_retry(url)
            if not response:
                return {}
            data = response.json()
            metadata = data.get('metadata', {})
            
            # Find the best image file (high-res original, not thumbnail)
            files = data.get('files', [])
            
            # Categorize by preference - originals first, then large derivatives
            originals = []
            derivatives = []
            for f in files:
                name = f.get('name', '')
                name_lower = name.lower()
                fmt = (f.get('format', '') or '').lower()
                source = (f.get('source', '') or '').lower()
                
                # Skip thumbnails and non-images
                if 'thumb' in name_lower or '_small' in name_lower or 'thumbnail' in fmt:
                    continue
                if not any(name_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.tif', '.tiff']):
                    continue
                
                size = int(f.get('size', 0) or 0)
                # Skip absurdly large or zero
                if size <= 0 or size > 30 * 1024 * 1024:
                    continue
                # Skip too small (likely thumbnails)
                if size < 50 * 1024:  # Under 50KB
                    continue
                
                entry = (size, name)
                if source == 'original':
                    originals.append(entry)
                else:
                    derivatives.append(entry)
            
            # Prefer originals (largest), fall back to derivatives
            best_image = None
            if originals:
                originals.sort(reverse=True)  # Largest first
                # But not too huge - pick largest under 10MB
                for size, name in originals:
                    if size < 10 * 1024 * 1024:
                        best_image = name
                        break
                if not best_image:
                    best_image = originals[0][1]
            elif derivatives:
                derivatives.sort(reverse=True)
                for size, name in derivatives:
                    if size < 10 * 1024 * 1024:
                        best_image = name
                        break
                if not best_image:
                    best_image = derivatives[0][1]
            
            full_image_url = None
            if best_image:
                full_image_url = f"https://archive.org/download/{identifier}/{best_image}"
            
            return {
                'metadata': metadata,
                'full_image_url': full_image_url
            }
        except Exception as e:
            print(f"Error fetching full metadata for {identifier}: {e}")
            return {}
    
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
        """Rank images by quality score AND metadata richness for better captions"""
        for img in images:
            score = img.get('quality', {}).get('quality_score', 50)
            
            # METADATA RICHNESS BOOST (critical for educational captions)
            # Strong descriptions = much better AI output
            desc = img.get('description') or img.get('alt_text') or ''
            if isinstance(desc, list):
                desc = ' '.join(str(d) for d in desc)
            if len(str(desc)) > 200:
                score += 25  # Rich description
            elif len(str(desc)) > 50:
                score += 12
            elif len(str(desc)) > 10:
                score += 5
            
            # Title quality (skip generic collection titles)
            title = str(img.get('title', ''))
            generic_phrases = ['medium: all', 'collections —', 'untitled', 'unknown']
            is_generic = any(g in title.lower() for g in generic_phrases)
            if title and len(title) > 15 and not is_generic:
                score += 15
            elif is_generic:
                score -= 20  # Penalize generic catalog titles
            
            # Creator/artist info available
            if img.get('creator'):
                score += 10
            
            # Date info available
            if img.get('date'):
                score += 8
            
            # Subject tags available
            subj = img.get('subject') or img.get('tags')
            if subj and (isinstance(subj, list) and len(subj) > 0 or isinstance(subj, str) and len(subj) > 0):
                score += 8
            
            # Source preference - archive.org items have richer metadata
            if 'archive.org' in str(img.get('parent_link', '')):
                score += 10
            
            # Add small randomness so ties are broken randomly (variety)
            score += random.uniform(0, 3)
            
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
        """Mark images as posted in database (creates entry if missing)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for url in urls:
            # Try UPDATE first
            cursor.execute('''
                UPDATE images 
                SET last_posted = ?, post_count = post_count + 1
                WHERE url = ?
            ''', (datetime.now(), url))
            
            # If no row was updated, INSERT a minimal record so dedup works
            if cursor.rowcount == 0:
                try:
                    cursor.execute('''
                        INSERT INTO images (url, source, scraped_at, last_posted, post_count)
                        VALUES (?, ?, ?, ?, 1)
                    ''', (url, 'unknown', datetime.now(), datetime.now()))
                except Exception as e:
                    print(f"Could not insert posted record for {url}: {e}")
            
            self.posted_urls.add(url)
        
        conn.commit()
        conn.close()
        print(f"📝 Marked {len(urls)} URL(s) as posted (total tracked: {len(self.posted_urls)})")
    
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
                # Use archive.org API - access thousands of images per collection
                images = self.scrape_archive_org_paginated(source, max_pages=max_pages_per_source, max_images=200)
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
