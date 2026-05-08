import requests
from bs4 import BeautifulSoup
import random
import time
from urllib.parse import urljoin, urlparse
import os
from typing import List, Dict, Tuple
import re

class ImageScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def scrape_archive_org(self, url: str, max_images: int = 10) -> List[Dict]:
        """Scrape images from archive.org pages"""
        images = []
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find image elements in archive.org
            img_tags = soup.find_all('img')
            
            for img in img_tags[:max_images * 2]:  # Get more to filter
                src = img.get('src') or img.get('data-src')
                if src and self._is_valid_image(src):
                    full_url = urljoin(url, src)
                    image_info = {
                        'url': full_url,
                        'source': self._get_archive_name(url),
                        'alt_text': img.get('alt', ''),
                        'title': soup.find('title').text if soup.find('title') else ''
                    }
                    images.append(image_info)
                    if len(images) >= max_images:
                        break
                        
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            
        return images
    
    def scrape_public_domain_review(self, url: str, max_images: int = 10) -> List[Dict]:
        """Scrape images from publicdomainreview.org"""
        images = []
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article images
            img_tags = soup.find_all('img', class_=re.compile(r'attachment|wp-image'))
            
            for img in img_tags[:max_images * 2]:
                src = img.get('src') or img.get('data-src')
                if src and self._is_valid_image(src):
                    full_url = urljoin(url, src)
                    image_info = {
                        'url': full_url,
                        'source': 'The Public Domain Review',
                        'alt_text': img.get('alt', ''),
                        'title': img.get('title', '')
                    }
                    images.append(image_info)
                    if len(images) >= max_images:
                        break
                    
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            
        return images
    
    def download_image(self, url: str, save_dir: str = 'temp_images') -> Tuple[str, str]:
        """Download image and return local path and filename"""
        os.makedirs(save_dir, exist_ok=True)
        
        try:
            response = self.session.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Get filename from URL
            parsed = urlparse(url)
            filename = os.path.basename(parsed.path)
            if not filename or '.' not in filename:
                filename = f"image_{int(time.time())}.jpg"
                
            local_path = os.path.join(save_dir, filename)
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            return local_path, filename
            
        except Exception as e:
            print(f"Error downloading image {url}: {e}")
            return None, None
    
    def _is_valid_image(self, url: str) -> bool:
        """Check if URL is a valid image"""
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return any(url.lower().endswith(ext) for ext in valid_extensions)
    
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
        else:
            return 'Internet Archive'
    
    def get_random_images(self, sources: List[str], count: int = 1) -> List[Dict]:
        """Get random images from multiple sources"""
        all_images = []
        
        for source in sources:
            if 'archive.org' in source:
                images = self.scrape_archive_org(source, max_images=5)
            elif 'publicdomainreview.org' in source:
                images = self.scrape_public_domain_review(source, max_images=5)
            else:
                continue
                
            all_images.extend(images)
            # Add small delay between sources
            time.sleep(random.uniform(1, 3))
        
        # Shuffle and return random selection
        random.shuffle(all_images)
        return all_images[:count]
