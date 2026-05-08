import unittest
from unittest.mock import Mock
import os
import sys
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analytics import AnalyticsEngine


class TestAnalyticsEngine(unittest.TestCase):
    """Test suite for analytics engine"""
    
    def setUp(self):
        # Use in-memory database for testing
        self.analytics = AnalyticsEngine(db_path=':memory:')
    
    def test_initialization(self):
        """Test analytics engine initializes"""
        self.assertIsNotNone(self.analytics.db_path)
    
    def test_track_post(self):
        """Test post tracking"""
        post_data = {
            'post_id': 'test_post_123',
            'platform': 'facebook',
            'image_url': 'https://example.com/image.jpg',
            'caption': 'Test caption',
            'posted_at': datetime.now(),
            'source': 'Test Archive',
            'category': 'art',
            'quality_score': 85.5
        }
        
        self.analytics.track_post(post_data)
        
        conn = sqlite3.connect(self.analytics.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM posts WHERE post_id = ?', ('test_post_123',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 'test_post_123')
        self.assertEqual(result[2], 'facebook')
    
    def test_record_engagement(self):
        """Test engagement recording"""
        # First track a post
        post_data = {
            'post_id': 'test_post_456',
            'platform': 'facebook',
            'image_url': 'https://example.com/image.jpg',
            'caption': 'Test caption',
            'posted_at': datetime.now()
        }
        self.analytics.track_post(post_data)
        
        # Record engagement
        metrics = {'likes': 100, 'comments': 20, 'shares': 5}
        self.analytics.record_engagement('test_post_456', metrics)
        
        conn = sqlite3.connect(self.analytics.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM engagement_metrics WHERE post_id = ?', ('test_post_456',))
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 3)  # 3 metrics recorded
    
    def test_get_post_performance(self):
        """Test post performance retrieval"""
        # Track a post
        post_data = {
            'post_id': 'test_post_789',
            'platform': 'facebook',
            'image_url': 'https://example.com/image.jpg',
            'caption': 'Test caption',
            'posted_at': datetime.now()
        }
        self.analytics.track_post(post_data)
        
        # Get performance
        performance = self.analytics.get_post_performance('test_post_789')
        
        self.assertIsNotNone(performance)
        self.assertIn('post', performance)
        self.assertIn('metrics', performance)
        self.assertEqual(performance['post']['post_id'], 'test_post_789')
    
    def test_get_post_performance_nonexistent(self):
        """Test performance retrieval for non-existent post"""
        performance = self.analytics.get_post_performance('nonexistent_post')
        
        self.assertIsNone(performance)
    
    def test_get_daily_summary(self):
        """Test daily summary generation"""
        # Track some posts
        for i in range(5):
            post_data = {
                'post_id': f'test_post_{i}',
                'platform': 'facebook',
                'image_url': 'https://example.com/image.jpg',
                'caption': 'Test caption',
                'posted_at': datetime.now()
            }
            self.analytics.track_post(post_data)
        
        summary = self.analytics.get_daily_summary(days=7)
        
        self.assertIsInstance(summary, list)
    
    def test_get_source_performance(self):
        """Test source performance analysis"""
        # Track posts from different sources
        sources = ['Archive1', 'Archive2', 'Archive3']
        for source in sources:
            post_data = {
                'post_id': f'post_{source}',
                'platform': 'facebook',
                'image_url': 'https://example.com/image.jpg',
                'caption': 'Test caption',
                'posted_at': datetime.now(),
                'source': source,
                'quality_score': 80.0
            }
            self.analytics.track_post(post_data)
        
        performance = self.analytics.get_source_performance()
        
        self.assertIn('sources', performance)
        self.assertIsInstance(performance['sources'], list)
    
    def test_get_category_performance(self):
        """Test category performance analysis"""
        # Track posts with categories
        categories = ['art', 'history', 'maps']
        for category in categories:
            post_data = {
                'post_id': f'post_{category}',
                'platform': 'facebook',
                'image_url': 'https://example.com/image.jpg',
                'caption': 'Test caption',
                'posted_at': datetime.now(),
                'category': category
            }
            self.analytics.track_post(post_data)
        
        performance = self.analytics.get_category_performance()
        
        self.assertIn('categories', performance)
        self.assertIsInstance(performance['categories'], list)
    
    def test_generate_report(self):
        """Test comprehensive report generation"""
        # Track some test data
        post_data = {
            'post_id': 'test_report_post',
            'platform': 'facebook',
            'image_url': 'https://example.com/image.jpg',
            'caption': 'Test caption',
            'posted_at': datetime.now(),
            'source': 'Test Archive',
            'category': 'art',
            'quality_score': 85.0
        }
        self.analytics.track_post(post_data)
        
        report = self.analytics.generate_report()
        
        self.assertIn('daily_summary', report)
        self.assertIn('top_content', report)
        self.assertIn('source_performance', report)
        self.assertIn('category_performance', report)
        self.assertIn('optimization_suggestions', report)
        self.assertIn('generated_at', report)
    
    def test_export_data_json(self):
        """Test data export as JSON"""
        report = self.analytics.generate_report()
        json_export = self.analytics.export_data(format='json')
        
        self.assertIsInstance(json_export, str)
        # Should be valid JSON
        import json
        parsed = json.loads(json_export)
        self.assertIsInstance(parsed, dict)


if __name__ == '__main__':
    unittest.main()
