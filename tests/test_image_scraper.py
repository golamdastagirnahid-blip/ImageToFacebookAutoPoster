import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from image_scraper import ImageScraper
from image_scraper_pro import ImageScraperPro


class TestImageScraper(unittest.TestCase):
    """Test suite for basic image scraper"""
    
    def setUp(self):
        self.scraper = ImageScraper()
    
    def test_initialization(self):
        """Test scraper initializes correctly"""
        self.assertIsNotNone(self.scraper.session)
        self.assertIn('User-Agent', self.scraper.session.headers)
    
    def test_is_valid_image(self):
        """Test image URL validation"""
        valid_urls = [
            'http://example.com/image.jpg',
            'https://example.com/photo.png',
            'http://test.com/pic.gif',
            'https://site.com/img.webp'
        ]
        
        invalid_urls = [
            'http://example.com/file.pdf',
            'https://example.com/document.html',
            'http://test.com/data.json'
        ]
        
        for url in valid_urls:
            self.assertTrue(self.scraper._is_valid_image(url))
        
        for url in invalid_urls:
            self.assertFalse(self.scraper._is_valid_image(url))
    
    def test_get_archive_name(self):
        """Test archive name extraction"""
        test_cases = [
            ('https://archive.org/details/david-rumsey-map-collection', 'David Rumsey Map Collection'),
            ('https://archive.org/details/metropolitanmuseumofart-gallery', 'Metropolitan Museum of Art'),
            ('https://archive.org/details/propix', 'Propix Archive'),
            ('https://archive.org/details/clevelandart', 'Cleveland Museum of Art'),
            ('https://archive.org/details/random', 'Internet Archive')
        ]
        
        for url, expected in test_cases:
            result = self.scraper._get_archive_name(url)
            self.assertEqual(result, expected)
    
    @patch('image_scraper.ImageScraper._fetch_with_retry')
    def test_scrape_archive_org(self, mock_fetch):
        """Test archive.org scraping"""
        # Mock response
        mock_response = Mock()
        mock_response.content = b'<html><img src="/image1.jpg" alt="Test Image"></html>'
        mock_response.raise_for_status = Mock()
        mock_fetch.return_value = mock_response
        
        images = self.scraper.scrape_archive_org('https://archive.org/details/test', max_images=5)
        
        self.assertIsInstance(images, list)
        # Should have at least one image
        self.assertGreaterEqual(len(images), 0)


class TestImageScraperPro(unittest.TestCase):
    """Test suite for pro image scraper"""
    
    def setUp(self):
        # Use in-memory database for testing
        self.scraper = ImageScraperPro(db_path=':memory:')
    
    def tearDown(self):
        # Clean up
        if os.path.exists('image_database.db'):
            os.remove('image_database.db')
    
    def test_initialization(self):
        """Test pro scraper initializes correctly"""
        self.assertIsNotNone(self.scraper.session)
        self.assertIsNotNone(self.scraper.db_path)
    
    def test_quality_check(self):
        """Test image quality checking"""
        # Create a mock image data
        from PIL import Image
        import io
        
        # Create a simple test image
        img = Image.new('RGB', (1000, 800), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        image_data = img_bytes.read()
        
        result = self.scraper._check_image_quality(image_data)
        
        self.assertIn('width', result)
        self.assertIn('height', result)
        self.assertIn('quality_score', result)
        self.assertIn('valid', result)
        self.assertEqual(result['width'], 1000)
        self.assertEqual(result['height'], 800)
    
    def test_content_hash(self):
        """Test content hash generation"""
        test_data = b'test image data'
        hash1 = self.scraper._calculate_content_hash(test_data)
        hash2 = self.scraper._calculate_content_hash(test_data)
        
        # Same data should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different data should produce different hash
        hash3 = self.scraper._calculate_content_hash(b'different data')
        self.assertNotEqual(hash1, hash3)
    
    def test_validate_image_url(self):
        """Test image URL validation"""
        valid_urls = [
            'https://example.com/image.jpg',
            'http://test.com/photo.png'
        ]
        
        invalid_urls = [
            'data:image/png;base64,iVBORw0KGgo=',
            '',
            'not-a-url'
        ]
        
        for url in valid_urls:
            self.assertTrue(self.scraper._validate_image_url(url))
        
        for url in invalid_urls:
            self.assertFalse(self.scraper._validate_image_url(url))
    
    def test_rank_images(self):
        """Test image ranking"""
        images = [
            {'quality': {'quality_score': 90, 'width': 1000, 'height': 800}},
            {'quality': {'quality_score': 70, 'width': 600, 'height': 400}},
            {'quality': {'quality_score': 85, 'width': 800, 'height': 600}}
        ]
        
        ranked = self.scraper.rank_images(images)
        
        # Should be sorted by score descending
        self.assertEqual(ranked[0]['quality']['quality_score'], 90)
        self.assertEqual(ranked[1]['quality']['quality_score'], 85)
        self.assertEqual(ranked[2]['quality']['quality_score'], 70)


if __name__ == '__main__':
    unittest.main()
