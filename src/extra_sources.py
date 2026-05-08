"""
Additional public-domain image sources beyond archive.org.
All free, no API key required (or free key already in code).
Each source returns a list of image dicts compatible with image_scraper_pro format:
    { url, source, title, alt_text, description, creator, identifier,
      parent_link, full_image_url, width, height, ... }
"""
import random
import requests
from typing import List, Dict


USER_AGENT = "Mozilla/5.0 (compatible; ArchivePosterBot/1.0; +https://github.com/)"


def _safe_get(url: str, params: dict = None, timeout: int = 20) -> dict:
    try:
        r = requests.get(url, params=params, timeout=timeout,
                         headers={'User-Agent': USER_AGENT})
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"   Source request failed: {e}")
        return {}


# ============================================================================
# 1. Library of Congress (16M+ items, free JSON API)
# ============================================================================
def fetch_library_of_congress(limit: int = 50) -> List[Dict]:
    """Library of Congress Free-to-Use sets - rotated random topics."""
    topics = [
        'photo,print,drawing',
        'maps',
        'manuscripts',
    ]
    topic = random.choice(topics)
    page = random.randint(1, 50)
    
    url = "https://www.loc.gov/photos/"
    params = {
        'q': topic,
        'fa': 'partof:free%20to%20use%20and%20reuse%20sets',
        'fo': 'json',
        'c': str(min(limit, 100)),
        'sp': str(page),
    }
    data = _safe_get(url, params)
    results = data.get('results', []) or []
    
    images = []
    for item in results:
        try:
            image_url = (item.get('image_url', []) or [None])[0]
            if not image_url:
                continue
            # Use largest thumbnail for high-quality posting
            if isinstance(item.get('image_url'), list) and len(item['image_url']) > 1:
                image_url = item['image_url'][-1]  # Last is usually largest
            
            title = item.get('title', '') or ''
            if not title:
                continue
            
            images.append({
                'url': image_url,
                'full_image_url': image_url,
                'source': 'Library of Congress',
                'title': title[:300],
                'alt_text': item.get('description', '') or title,
                'description': ' '.join(item.get('description', []) or []) if isinstance(item.get('description'), list) else (item.get('description') or ''),
                'creator': ', '.join(item.get('contributor', [])[:3]) if item.get('contributor') else '',
                'date': item.get('date', '') or '',
                'subject': ', '.join(item.get('subject', [])[:5]) if item.get('subject') else '',
                'identifier': item.get('id', ''),
                'parent_link': item.get('url', '') or item.get('id', ''),
                'rights': 'Public Domain (Library of Congress)',
                'publisher': 'Library of Congress',
                'width': 1200,
                'height': 800,
            })
        except Exception as e:
            print(f"   LoC item parse error: {e}")
            continue
    print(f"📚 Library of Congress: {len(images)} items")
    return images


# ============================================================================
# 2. Smithsonian Open Access (4.5M+ items, free key)
# ============================================================================
def fetch_smithsonian(limit: int = 50, api_key: str = None) -> List[Dict]:
    """Smithsonian Open Access (CC0). Requires free API key from data.gov."""
    import os
    api_key = api_key or os.getenv('SMITHSONIAN_API_KEY', '').strip() or os.getenv('DATA_GOV_API_KEY', '').strip()
    if not api_key:
        # DEMO_KEY works but is heavily rate-limited
        api_key = 'DEMO_KEY'
    
    rows = min(limit, 100)
    start = random.randint(0, 5000)
    
    # Search for items with images, in public domain
    url = "https://api.si.edu/openaccess/api/v1.0/search"
    params = {
        'api_key': api_key,
        'q': 'online_media_type:"Images" AND unit_code:NPG OR unit_code:SAAM OR unit_code:CHNDM',
        'rows': rows,
        'start': start,
    }
    data = _safe_get(url, params)
    rows_data = (data.get('response', {}) or {}).get('rows', []) or []
    
    images = []
    for item in rows_data:
        try:
            content = item.get('content', {}) or {}
            descriptive = content.get('descriptiveNonRepeating', {}) or {}
            online_media = descriptive.get('online_media', {}) or {}
            media_list = online_media.get('media', []) or []
            
            if not media_list:
                continue
            media = media_list[0]
            image_url = (media.get('content') or '').replace('http://', 'https://')
            if not image_url:
                continue
            
            title = item.get('title', '') or descriptive.get('title', {}).get('content', '')
            if not title:
                continue
            
            indexed = content.get('indexedStructured', {}) or {}
            
            images.append({
                'url': image_url,
                'full_image_url': image_url,
                'source': 'Smithsonian',
                'title': str(title)[:300],
                'alt_text': str(title),
                'description': str(content.get('freetext', {}).get('notes', [{}])[0].get('content', '')) if content.get('freetext', {}).get('notes') else '',
                'creator': ', '.join(indexed.get('name', [])[:3]) if indexed.get('name') else '',
                'date': ', '.join(indexed.get('date', [])[:2]) if indexed.get('date') else '',
                'subject': ', '.join(indexed.get('topic', [])[:5]) if indexed.get('topic') else '',
                'identifier': item.get('id', ''),
                'parent_link': descriptive.get('record_link', ''),
                'rights': 'CC0 (Smithsonian Open Access)',
                'publisher': 'Smithsonian Institution',
                'width': 1200,
                'height': 800,
            })
        except Exception as e:
            print(f"   Smithsonian item parse error: {e}")
            continue
    print(f"📚 Smithsonian: {len(images)} items")
    return images


# ============================================================================
# 3. NASA Image Library (140K+ items, no key required)
# ============================================================================
def fetch_nasa(limit: int = 50) -> List[Dict]:
    """NASA Image and Video Library."""
    # Search rotated topics for variety
    topics = ['galaxy', 'nebula', 'mars', 'earth', 'moon', 'apollo',
              'astronaut', 'space station', 'jupiter', 'saturn', 'sun',
              'hubble', 'telescope', 'rocket', 'aurora']
    topic = random.choice(topics)
    page = random.randint(1, 10)
    
    url = "https://images-api.nasa.gov/search"
    params = {
        'q': topic,
        'media_type': 'image',
        'page': page,
        'page_size': min(limit, 100),
    }
    data = _safe_get(url, params)
    items = (data.get('collection', {}) or {}).get('items', []) or []
    
    images = []
    for item in items:
        try:
            data_list = item.get('data', []) or []
            if not data_list:
                continue
            d = data_list[0]
            
            links = item.get('links', []) or []
            preview = next((l['href'] for l in links if l.get('rel') == 'preview'), None)
            if not preview:
                continue
            
            # Try to get higher-res original (replace ~thumb.jpg with ~orig.jpg)
            full_url = preview.replace('~thumb.jpg', '~orig.jpg').replace('~small.jpg', '~orig.jpg')
            
            title = d.get('title', '') or ''
            if not title:
                continue
            
            images.append({
                'url': preview,
                'full_image_url': full_url,
                'source': 'NASA',
                'title': title[:300],
                'alt_text': d.get('description_508', '') or d.get('description', '')[:500],
                'description': d.get('description', '') or '',
                'creator': d.get('photographer', '') or d.get('center', 'NASA'),
                'date': (d.get('date_created', '') or '')[:10],
                'subject': ', '.join((d.get('keywords', []) or [])[:6]),
                'identifier': d.get('nasa_id', ''),
                'parent_link': f"https://images.nasa.gov/details/{d.get('nasa_id', '')}",
                'rights': 'Public Domain (NASA)',
                'publisher': d.get('center', 'NASA'),
                'width': 1920,
                'height': 1080,
            })
        except Exception as e:
            print(f"   NASA item parse error: {e}")
            continue
    print(f"📚 NASA: {len(images)} items")
    return images


# ============================================================================
# 4. Metropolitan Museum of Art Open Access (492K+ public domain artworks)
# ============================================================================
_MET_OBJECT_IDS_CACHE = []

def fetch_met_museum(limit: int = 50) -> List[Dict]:
    """Met Museum Open Access. Random art objects with public-domain images."""
    global _MET_OBJECT_IDS_CACHE
    
    # Cache the master list of all public-domain object IDs
    if not _MET_OBJECT_IDS_CACHE:
        url = "https://collectionapi.metmuseum.org/public/collection/v1/search"
        params = {'hasImages': 'true', 'isPublicDomain': 'true', 'q': 'painting'}
        data = _safe_get(url, params)
        ids = data.get('objectIDs', []) or []
        if ids:
            _MET_OBJECT_IDS_CACHE = ids
    
    if not _MET_OBJECT_IDS_CACHE:
        print("📚 Met Museum: failed to fetch ID list")
        return []
    
    sample_ids = random.sample(_MET_OBJECT_IDS_CACHE,
                                min(limit, len(_MET_OBJECT_IDS_CACHE)))
    
    images = []
    for oid in sample_ids:
        try:
            obj_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}"
            obj = _safe_get(obj_url)
            if not obj or not obj.get('isPublicDomain'):
                continue
            primary = obj.get('primaryImage', '')
            if not primary:
                continue
            
            images.append({
                'url': obj.get('primaryImageSmall', primary),
                'full_image_url': primary,
                'source': 'Metropolitan Museum of Art',
                'title': (obj.get('title', '') or '')[:300],
                'alt_text': obj.get('title', ''),
                'description': obj.get('objectName', ''),
                'creator': obj.get('artistDisplayName', '') or obj.get('culture', ''),
                'date': obj.get('objectDate', '') or '',
                'subject': ', '.join([t.get('term', '') for t in obj.get('tags', []) or []][:5]),
                'identifier': str(oid),
                'parent_link': obj.get('objectURL', ''),
                'rights': 'Public Domain (Met Museum)',
                'publisher': 'Metropolitan Museum of Art',
                'width': 1500,
                'height': 1200,
            })
            if len(images) >= limit:
                break
        except Exception as e:
            continue
    print(f"📚 Met Museum: {len(images)} items")
    return images


# ============================================================================
# Master function: fetch from all extra sources
# ============================================================================
def fetch_all_extra_sources(per_source_limit: int = 30) -> List[Dict]:
    """Fetch images from all extra (non-archive.org) sources."""
    all_images = []
    
    fetchers = [
        ('Library of Congress', fetch_library_of_congress),
        ('NASA', fetch_nasa),
        ('Met Museum', fetch_met_museum),
        ('Smithsonian', fetch_smithsonian),
    ]
    
    for name, fn in fetchers:
        try:
            results = fn(limit=per_source_limit)
            all_images.extend(results)
        except Exception as e:
            print(f"❌ {name} fetcher failed: {e}")
            continue
    
    return all_images
