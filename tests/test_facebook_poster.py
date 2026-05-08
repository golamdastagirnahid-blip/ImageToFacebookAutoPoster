import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from facebook_poster import FacebookPoster


class TestFacebookPoster(unittest.TestCase):
    """Test suite for Facebook poster"""
    
    @patch.dict(os.environ, {'FACEBOOK_ACCESS_TOKEN': 'test_token', 'FACEBOOK_PAGE_ID': '123456'})
    def setUp(self):
        self.poster = FacebookPoster()
    
    def test_initialization(self):
        """Test poster initializes correctly"""
        self.assertEqual(self.poster.access_token, 'test_token')
        self.assertEqual(self.poster.page_id, '123456')
        self.assertIn('facebook.com', self.poster.base_url)
    
    def test_initialization_without_credentials(self):
        """Test initialization fails without credentials"""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                FacebookPoster()
    
    @patch('facebook_poster.requests.post')
    def test_post_image_success(self, mock_post):
        """Test successful image posting"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {'id': 'test_post_123'}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        # Create a test image file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jpg', delete=False) as f:
            test_path = f.name
            f.write('fake image data')
        
        try:
            result = self.poster.post_image(test_path, 'Test caption')
            
            self.assertIn('id', result)
            self.assertEqual(result['id'], 'test_post_123')
            mock_post.assert_called_once()
        finally:
            os.unlink(test_path)
    
    @patch('facebook_poster.requests.post')
    def test_post_image_failure(self, mock_post):
        """Test image posting failure"""
        # Mock failed response
        mock_post.side_effect = Exception('Network error')
        
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jpg', delete=False) as f:
            test_path = f.name
            f.write('fake image data')
        
        try:
            result = self.poster.post_image(test_path, 'Test caption')
            
            self.assertIn('error', result)
        finally:
            os.unlink(test_path)
    
    @patch('facebook_poster.requests.get')
    def test_test_connection_success(self, mock_get):
        """Test successful connection test"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        result = self.poster.test_connection()
        
        self.assertTrue(result)
        mock_get.assert_called_once()
    
    @patch('facebook_poster.requests.get')
    def test_test_connection_failure(self, mock_get):
        """Test connection test failure"""
        mock_get.side_effect = Exception('Connection failed')
        
        result = self.poster.test_connection()
        
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
