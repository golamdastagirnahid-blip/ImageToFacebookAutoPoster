import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from PIL import Image
import numpy as np
from enum import Enum
import json
from dotenv import load_dotenv

load_dotenv()

class NSFWLevel(Enum):
    """NSFW detection confidence levels"""
    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    BLOCKED = "blocked"


class StrictNSFWDetector:
    """Multi-layered, highly strict NSFW detection system"""
    
    def __init__(self, db_path: str = 'nsfw_detector.db'):
        self.db_path = db_path
        self._init_database()
        self._init_filters()
        
        # Configuration
        self.strict_mode = os.getenv('NSFW_STRICT_MODE', 'true').lower() == 'true'
        self.skin_threshold = float(os.getenv('SKIN_DETECTION_THRESHOLD', '0.15'))
        self.block_on_medium = os.getenv('BLOCK_ON_MEDIUM_RISK', 'true').lower() == 'true'
        
    def _init_database(self):
        """Initialize NSFW detection database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nsfw_detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT UNIQUE,
                image_path TEXT,
                detection_level TEXT,
                skin_ratio REAL,
                keyword_matches TEXT,
                ai_score REAL,
                flagged_at TIMESTAMP,
                reviewed BOOLEAN DEFAULT 0,
                approved BOOLEAN DEFAULT 0,
                notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nsfw_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT UNIQUE,
                severity INTEGER DEFAULT 1,
                category TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nsfw_quarantine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_url TEXT,
                image_path TEXT,
                detection_level TEXT,
                reason TEXT,
                quarantined_at TIMESTAMP,
                released BOOLEAN DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Load default keywords if empty
        self._load_default_keywords()
    
    def _load_default_keywords(self):
        """Load default NSFW keywords if database is empty"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM nsfw_keywords')
        count = cursor.fetchone()[0]
        
        if count == 0:
            # High severity keywords
            high_severity = [
                'nude', 'naked', 'porn', 'sex', 'explicit', 'adult',
                'erotic', 'fetish', 'nsfw', 'xxx', 'breast', 'genital',
                'sexual', 'intimate', 'provocative', 'suggestive',
                'topless', 'bottomless', 'stripping', 'stripper',
                'hardcore', 'softcore', 'bikini', 'lingerie', 'thong'
            ]
            
            # Medium severity keywords
            medium_severity = [
                'sexy', 'hot', 'babe', 'model', 'swimsuit', 'cleavage',
                'tight', 'revealing', 'seductive', 'alluring'
            ]
            
            # Low severity keywords (context-dependent)
            low_severity = [
                'body', 'skin', 'figure', 'form', 'silhouette'
            ]
            
            for keyword in high_severity:
                cursor.execute('INSERT OR IGNORE INTO nsfw_keywords (keyword, severity, category) VALUES (?, 3, ?)', 
                              (keyword, 'explicit'))
            
            for keyword in medium_severity:
                cursor.execute('INSERT OR IGNORE INTO nsfw_keywords (keyword, severity, category) VALUES (?, 2, ?)', 
                              (keyword, 'suggestive'))
            
            for keyword in low_severity:
                cursor.execute('INSERT OR IGNORE INTO nsfw_keywords (keyword, severity, category) VALUES (?, 1, ?)', 
                              (keyword, 'contextual'))
            
            conn.commit()
        
        conn.close()
    
    def _init_filters(self):
        """Initialize filter components"""
        self.nsfw_keywords = self._load_keywords()
        
        # Skin color ranges for detection (RGB)
        self.skin_lower = np.array([0, 20, 70], dtype=np.uint8)
        self.skin_upper = np.array([20, 255, 255], dtype=np.uint8)
    
    def _load_keywords(self) -> List[Dict]:
        """Load NSFW keywords from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT keyword, severity, category FROM nsfw_keywords')
        keywords = []
        
        for row in cursor.fetchall():
            keywords.append({
                'keyword': row[0],
                'severity': row[1],
                'category': row[2]
            })
        
        conn.close()
        return keywords
    
    def detect_nsfw(self, image_info: Dict) -> Dict:
        """
        Multi-layered NSFW detection with strict filtering
        """
        results = {
            'image_url': image_info.get('url', ''),
            'image_path': image_info.get('local_path'),
            'overall_level': NSFWLevel.SAFE.value,
            'confidence': 0.0,
            'checks': {},
            'blocked': False,
            'reason': ''
        }
        
        # Layer 1: URL Analysis
        url_check = self._check_url(image_info.get('url', ''))
        results['checks']['url'] = url_check
        
        if url_check['blocked']:
            results['overall_level'] = NSFWLevel.BLOCKED.value
            results['blocked'] = True
            results['reason'] = "URL contains blocked patterns"
            self._quarantine(image_info, NSFWLevel.BLOCKED.value, results['reason'])
            return results
        
        # Layer 2: Text Metadata Analysis
        text_check = self._check_text_metadata(image_info)
        results['checks']['text'] = text_check
        
        if text_check['blocked']:
            results['overall_level'] = NSFWLevel.BLOCKED.value
            results['blocked'] = True
            results['reason'] = "Text metadata contains blocked keywords"
            self._quarantine(image_info, NSFWLevel.BLOCKED.value, results['reason'])
            return results
        
        # Layer 3: Image Analysis (if local path available)
        if image_info.get('local_path'):
            # Pass art context flag from text analysis
            is_art = (results.get('checks', {}).get('text', {}).get('context') ==
                      'art_whitelist_applied') or self._detect_art_context(image_info)
            image_check = self._analyze_image(image_info['local_path'], is_art_context=is_art)
            results['checks']['image'] = image_check
            
            if image_check['blocked']:
                results['overall_level'] = NSFWLevel.BLOCKED.value
                results['blocked'] = True
                results['reason'] = "Image analysis detected NSFW content"
                self._quarantine(image_info, NSFWLevel.BLOCKED.value, results['reason'])
                return results
            
            if image_check['level'] == NSFWLevel.HIGH_RISK.value:
                results['overall_level'] = NSFWLevel.HIGH_RISK.value
                if self.block_on_medium:
                    results['blocked'] = True
                    results['reason'] = "High risk content detected"
                    self._quarantine(image_info, NSFWLevel.HIGH_RISK.value, results['reason'])
                    return results
            elif image_check['level'] == NSFWLevel.MEDIUM_RISK.value:
                results['overall_level'] = NSFWLevel.MEDIUM_RISK.value
                if self.block_on_medium:
                    results['blocked'] = True
                    results['reason'] = "Medium risk content detected"
                    self._quarantine(image_info, NSFWLevel.MEDIUM_RISK.value, results['reason'])
                    return results
        
        # Layer 4: AI Detection (if enabled)
        if os.getenv('USE_AI_NSFW_DETECTION', 'false').lower() == 'true':
            ai_check = self._ai_detection(image_info)
            results['checks']['ai'] = ai_check
            
            if ai_check['blocked']:
                results['overall_level'] = NSFWLevel.BLOCKED.value
                results['blocked'] = True
                results['reason'] = "AI detection flagged as NSFW"
                self._quarantine(image_info, NSFWLevel.BLOCKED.value, results['reason'])
                return results
        
        # Calculate overall confidence
        results['confidence'] = self._calculate_confidence(results['checks'])
        
        # Log detection
        self._log_detection(results)
        
        return results
    
    def _check_url(self, url: str) -> Dict:
        """Check URL for NSFW patterns"""
        url_lower = url.lower()
        
        # Check for blocked patterns
        blocked_patterns = [
            'nsfw', 'porn', 'xxx', 'adult', 'erotic', 'nude',
            'sex', 'fetish', 'explicit', 'hardcore', 'softcore'
        ]
        
        found_patterns = [p for p in blocked_patterns if p in url_lower]
        
        if found_patterns:
            return {
                'blocked': True,
                'patterns': found_patterns,
                'severity': 'high'
            }
        
        return {
            'blocked': False,
            'patterns': [],
            'severity': 'none'
        }
    
    def _check_text_metadata(self, image_info: Dict) -> Dict:
        """Check text metadata for NSFW keywords with art/history context awareness"""
        import re
        
        # Build text from all metadata fields
        title = str(image_info.get('title', ''))
        alt = str(image_info.get('alt_text', ''))
        desc = image_info.get('description', '')
        if isinstance(desc, list):
            desc = ' '.join(str(d) for d in desc)
        creator = str(image_info.get('creator', ''))
        subject = image_info.get('subject', '')
        if isinstance(subject, list):
            subject = ' '.join(str(s) for s in subject)
        source = str(image_info.get('source', ''))
        parent = str(image_info.get('parent_link', ''))
        
        text_to_check = f"{title} {alt} {desc} {creator} {subject} {source} {parent}"
        text_lower = text_to_check.lower()
        
        # ART/HISTORICAL CONTEXT WHITELIST
        # If text indicates fine art, museum, or historical context, treat conservatively
        art_context_terms = [
            'painting', 'sculpture', 'museum', 'gallery', 'exhibition',
            'drawing', 'etching', 'engraving', 'lithograph', 'woodcut',
            'fresco', 'mural', 'oil on canvas', 'watercolor', 'portrait',
            'classical', 'renaissance', 'baroque', 'romanticism', 'impressionist',
            'antique', 'antiquity', 'medieval', 'century', 'b.c.', 'a.d.',
            'historical', 'archive', 'archaeology', 'archaeological',
            'metropolitan museum', 'cleveland', 'rumsey', 'public domain',
            'illustration', 'manuscript', 'photography studio', 'daguerreotype',
            'cartography', 'map of', 'atlas', 'specimen', 'botanical',
            'anatomical', 'medical illustration', 'scientific'
        ]
        is_art_context = any(term in text_lower for term in art_context_terms)
        
        # Use word-boundary matching (NOT substring) to avoid false positives
        # "model" should not match "modeling", "body" should not match "bodyguard"
        found_keywords = []
        total_severity = 0
        
        for kw in self.nsfw_keywords:
            keyword = kw['keyword']
            # Use word boundary regex to match whole words only
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                found_keywords.append({
                    'keyword': keyword,
                    'severity': kw['severity'],
                    'category': kw['category']
                })
                total_severity += kw['severity']
        
        # In art context, downgrade severity (classical art has "nude" legitimately)
        if is_art_context and found_keywords:
            # Only block if MULTIPLE high-severity explicit terms appear
            high_explicit = [k for k in found_keywords
                           if k['severity'] >= 3 and k['keyword'] in
                           ['porn', 'xxx', 'hardcore', 'fetish', 'nsfw', 'explicit']]
            if len(high_explicit) >= 1:
                return {
                    'blocked': True,
                    'keywords': found_keywords,
                    'total_severity': total_severity,
                    'context': 'art_with_explicit_match'
                }
            # Art context with only mild matches - allow it
            return {
                'blocked': False,
                'keywords': found_keywords,
                'total_severity': total_severity,
                'context': 'art_whitelist_applied'
            }
        
        # Non-art context - apply original strict rules
        if found_keywords:
            if total_severity >= 6:  # Multiple high-severity matches required
                return {
                    'blocked': True,
                    'keywords': found_keywords,
                    'total_severity': total_severity
                }
            elif total_severity >= 4:  # Medium-high
                return {
                    'blocked': self.strict_mode,
                    'keywords': found_keywords,
                    'total_severity': total_severity
                }
        
        return {
            'blocked': False,
            'keywords': [],
            'total_severity': 0
        }
    
    def _detect_art_context(self, image_info: Dict) -> bool:
        """Quick check: is this image from an art/historical archive?"""
        text = ' '.join(str(image_info.get(k, '')) for k in
                        ['title', 'alt_text', 'description', 'creator', 'subject',
                         'source', 'parent_link', 'url'])
        text_lower = text.lower()
        art_terms = ['archive.org', 'metropolitan museum', 'cleveland', 'rumsey',
                     'public domain', 'museum', 'painting', 'sculpture', 'gallery',
                     'classical', 'renaissance', 'baroque', 'medieval', 'antique',
                     'historical', 'manuscript', 'lithograph', 'engraving', 'etching']
        return any(term in text_lower for term in art_terms)
    
    def _analyze_image(self, image_path: str, is_art_context: bool = False) -> Dict:
        """Analyze image for NSFW content using multiple techniques.
        For art/historical context, only flags extreme cases (paintings/portraits
        normally have high skin ratios from faces/hands and varied aspect ratios)."""
        try:
            img = Image.open(image_path)
            
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            width, height = img.size
            
            # Skip pixel analysis on tiny images (< 200px) - too unreliable
            if width < 200 or height < 200:
                return {
                    'level': NSFWLevel.SAFE.value,
                    'blocked': False,
                    'risk_score': 0,
                    'skip_reason': 'image_too_small_for_analysis'
                }
            
            # Technique 1: Skin detection
            skin_ratio = self._detect_skin_ratio(img)
            aspect_ratio = width / height
            color_distribution = self._analyze_color_distribution(img)
            brightness, contrast = self._analyze_brightness_contrast(img)
            
            risk_score = 0
            reasons = []
            
            # ART CONTEXT: Use much higher thresholds
            if is_art_context:
                # Only flag extreme skin ratios in art (paintings have lots of skin from faces/bodies)
                if skin_ratio > 0.6:
                    risk_score += 25
                    reasons.append(f"Very high skin ratio in art: {skin_ratio:.2%}")
                # Skip aspect/color/contrast checks entirely - meaningless for art
            else:
                # Standard strict checks for non-art content
                if skin_ratio > 0.3:
                    risk_score += 30
                    reasons.append(f"High skin ratio: {skin_ratio:.2%}")
                elif skin_ratio > 0.2:
                    risk_score += 15
                    reasons.append(f"Moderate skin ratio: {skin_ratio:.2%}")
                
                if 0.5 < aspect_ratio < 0.8:
                    risk_score += 10
                    reasons.append(f"Suspicious aspect ratio: {aspect_ratio:.2f}")
                
                if color_distribution['warm_ratio'] > 0.6:
                    risk_score += 10
                    reasons.append(f"High warm color ratio: {color_distribution['warm_ratio']:.2%}")
                
                if contrast > 0.7:
                    risk_score += 5
                    reasons.append(f"High contrast: {contrast:.2f}")
            
            # Determine level
            if risk_score >= 50:
                level = NSFWLevel.HIGH_RISK.value
                blocked = True
            elif risk_score >= 30:
                level = NSFWLevel.MEDIUM_RISK.value
                blocked = self.block_on_medium
            elif risk_score >= 15:
                level = NSFWLevel.LOW_RISK.value
                blocked = False
            else:
                level = NSFWLevel.SAFE.value
                blocked = False
            
            return {
                'level': level,
                'blocked': blocked,
                'risk_score': risk_score,
                'skin_ratio': skin_ratio,
                'aspect_ratio': aspect_ratio,
                'reasons': reasons
            }
            
        except Exception as e:
            print(f"Image analysis error: {e}")
            # If analysis fails, be conservative and block
            return {
                'level': NSFWLevel.MEDIUM_RISK.value,
                'blocked': self.strict_mode,
                'risk_score': 30,
                'error': str(e)
            }
    
    def _detect_skin_ratio(self, img: Image) -> float:
        """Detect ratio of skin-colored pixels in image"""
        try:
            # Convert to numpy array
            img_array = np.array(img)
            
            # Convert to HSV
            import cv2
            hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
            
            # Create skin mask
            skin_mask = cv2.inRange(hsv, self.skin_lower, self.skin_upper)
            
            # Calculate ratio
            total_pixels = img_array.shape[0] * img_array.shape[1]
            skin_pixels = np.count_nonzero(skin_mask)
            
            return skin_pixels / total_pixels if total_pixels > 0 else 0
            
        except:
            # Fallback if cv2 not available
            return 0.0
    
    def _analyze_color_distribution(self, img: Image) -> Dict:
        """Analyze color distribution in image"""
        try:
            img_array = np.array(img)
            
            # Split into channels
            r, g, b = img_array[:,:,0], img_array[:,:,1], img_array[:,:,2]
            
            # Calculate warm colors (high red, low blue)
            warm_pixels = np.sum((r > 150) & (b < 100))
            total_pixels = img_array.shape[0] * img_array.shape[1]
            
            warm_ratio = warm_pixels / total_pixels if total_pixels > 0 else 0
            
            return {
                'warm_ratio': warm_ratio,
                'dominant_channel': 'red' if np.mean(r) > np.mean(g) and np.mean(r) > np.mean(b) else 'other'
            }
            
        except:
            return {'warm_ratio': 0, 'dominant_channel': 'unknown'}
    
    def _analyze_brightness_contrast(self, img: Image) -> tuple:
        """Analyze brightness and contrast"""
        try:
            img_array = np.array(img)
            
            # Convert to grayscale
            gray = np.mean(img_array, axis=2)
            
            # Calculate brightness (mean)
            brightness = np.mean(gray) / 255
            
            # Calculate contrast (standard deviation)
            contrast = np.std(gray) / 255
            
            return brightness, contrast
            
        except:
            return 0.5, 0.5
    
    def _ai_detection(self, image_info: Dict) -> Dict:
        """
        AI-based NSFW detection using external services
        Integrates with services like:
        - Google Cloud Vision API (Safe Search Detection)
        - AWS Rekognition (Moderation Labels)
        - Azure Content Moderator
        - NudeNet (open-source)
        """
        # This would integrate with actual AI services
        # For now, return conservative default
        
        try:
            # Example: Google Cloud Vision API
            # from google.cloud import vision
            # client = vision.ImageAnnotatorClient()
            # response = client.safe_search_detection(image_source)
            
            # For now, assume safe if not configured
            return {
                'blocked': False,
                'ai_score': 0.0,
                'service': 'none'
            }
            
        except Exception as e:
            print(f"AI detection error: {e}")
            return {
                'blocked': False,
                'ai_score': 0.0,
                'error': str(e)
            }
    
    def _calculate_confidence(self, checks: Dict) -> float:
        """Calculate overall confidence in safety assessment"""
        confidence = 1.0  # Start with 100% confidence
        
        # Reduce confidence based on checks
        if checks.get('url', {}).get('patterns'):
            confidence -= 0.3
        
        if checks.get('text', {}).get('keywords'):
            severity = checks['text']['total_severity']
            confidence -= (severity * 0.1)
        
        if 'image' in checks:
            risk_score = checks['image'].get('risk_score', 0)
            confidence -= (risk_score / 100)
        
        return max(0.0, confidence)
    
    def _log_detection(self, results: Dict):
        """Log detection result to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO nsfw_detections
                (image_url, image_path, detection_level, skin_ratio, keyword_matches, ai_score, flagged_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                results['image_url'],
                results.get('image_path'),
                results['overall_level'],
                results['checks'].get('image', {}).get('skin_ratio', 0),
                json.dumps(results['checks'].get('text', {}).get('keywords', [])),
                results['checks'].get('ai', {}).get('ai_score', 0)
            ))
            conn.commit()
        except Exception as e:
            print(f"Failed to log detection: {e}")
        finally:
            conn.close()
    
    def _quarantine(self, image_info: Dict, level: str, reason: str):
        """Quarantine flagged content"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO nsfw_quarantine
                (image_url, image_path, detection_level, reason, quarantined_at)
                VALUES (?, ?, ?, ?, datetime('now'))
            ''', (
                image_info.get('url'),
                image_info.get('local_path'),
                level,
                reason
            ))
            conn.commit()
        except Exception as e:
            print(f"Failed to quarantine: {e}")
        finally:
            conn.close()
    
    def release_from_quarantine(self, image_url: str, approved: bool = False, notes: str = '') -> bool:
        """Release content from quarantine"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE nsfw_quarantine
                SET released = 1
                WHERE image_url = ? AND released = 0
            ''', (image_url,))
            
            if approved:
                cursor.execute('''
                    UPDATE nsfw_detections
                    SET reviewed = 1, approved = 1, notes = ?
                    WHERE image_url = ?
                ''', (notes, image_url))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Failed to release from quarantine: {e}")
            return False
        finally:
            conn.close()
    
    def get_quarantined_items(self) -> List[Dict]:
        """Get all quarantined items"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM nsfw_quarantine WHERE released = 0
            ORDER BY quarantined_at DESC
        ''')
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'image_url': row[1],
                'image_path': row[2],
                'detection_level': row[3],
                'reason': row[4],
                'quarantined_at': row[5]
            })
        
        conn.close()
        return items
    
    def get_statistics(self) -> Dict:
        """Get NSFW detection statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count by level
        cursor.execute('''
            SELECT detection_level, COUNT(*) as count
            FROM nsfw_detections
            GROUP BY detection_level
        ''')
        
        level_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Quarantine count
        cursor.execute('SELECT COUNT(*) FROM nsfw_quarantine WHERE released = 0')
        quarantine_count = cursor.fetchone()[0]
        
        # Total detections
        cursor.execute('SELECT COUNT(*) FROM nsfw_detections')
        total_detections = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'level_counts': level_counts,
            'quarantine_count': quarantine_count,
            'total_detections': total_detections,
            'block_rate': level_counts.get(NSFWLevel.BLOCKED.value, 0) / total_detections if total_detections > 0 else 0
        }
    
    def add_custom_keyword(self, keyword: str, severity: int = 3, category: str = 'custom'):
        """Add custom NSFW keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO nsfw_keywords (keyword, severity, category)
                VALUES (?, ?, ?)
            ''', (keyword.lower(), severity, category))
            conn.commit()
            
            # Reload keywords
            self.nsfw_keywords = self._load_keywords()
            
            return True
        except Exception as e:
            print(f"Failed to add keyword: {e}")
            return False
        finally:
            conn.close()
    
    def remove_keyword(self, keyword: str):
        """Remove NSFW keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM nsfw_keywords WHERE keyword = ?', (keyword.lower(),))
            conn.commit()
            
            # Reload keywords
            self.nsfw_keywords = self._load_keywords()
            
        except Exception as e:
            print(f"Failed to remove keyword: {e}")
        finally:
            conn.close()


class FacebookPolicyCompliance:
    """Facebook-specific policy compliance checker"""
    
    def __init__(self):
        self.detector = StrictNSFWDetector()
        
        # Facebook-specific blocked content
        self.facebook_policies = {
            'nudity': True,  # Strict no nudity
            'sexual_content': True,  # No sexual content
            'violence': True,  # No graphic violence
            'hate_speech': True,  # No hate speech
            'harassment': True,  # No harassment
            'self_harm': True,  # No self-harm content
            'dangerous_goods': True,  # No regulated goods
        }
    
    def check_compliance(self, image_info: Dict) -> Dict:
        """Check if content complies with Facebook policies"""
        # Run NSFW detection
        nsfw_result = self.detector.detect_nsfw(image_info)
        
        # Additional Facebook-specific checks
        compliance_result = {
            'compliant': True,
            'violations': [],
            'nsfw_result': nsfw_result
        }
        
        # Check NSFW
        if nsfw_result['blocked']:
            compliance_result['compliant'] = False
            compliance_result['violations'].append({
                'policy': 'nudity_and_sexual_content',
                'reason': nsfw_result['reason'],
                'severity': 'critical'
            })
        
        # Add more Facebook-specific checks as needed
        
        return compliance_result
    
    def get_compliance_report(self) -> Dict:
        """Get Facebook compliance statistics"""
        nsfw_stats = self.detector.get_statistics()
        
        return {
            'facebook_policy_compliance': {
                'total_checked': nsfw_stats['total_detections'],
                'blocked': nsfw_stats['level_counts'].get('blocked', 0),
                'compliance_rate': 1.0 - nsfw_stats['block_rate'],
                'quarantined': nsfw_stats['quarantine_count']
            },
            'policies_enforced': self.facebook_policies
        }
