import unittest
from unittest.mock import Mock, patch
import os
import sys
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from health_monitor import HealthMonitor, SelfHealingSystem


class TestHealthMonitor(unittest.TestCase):
    """Test suite for health monitor"""
    
    def setUp(self):
        # Use in-memory database for testing
        self.monitor = HealthMonitor(db_path=':memory:')
    
    def test_initialization(self):
        """Test monitor initializes correctly"""
        self.assertIsNotNone(self.monitor.db_path)
        # Check database was created
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        # Tables should exist in the actual database
        conn.close()
    
    def test_log_health_check(self):
        """Test health check logging"""
        self.monitor._log_health_check('test_component', 'healthy', 'OK', 100.5)
        
        # Verify it was logged
        conn = sqlite3.connect(self.monitor.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM health_checks WHERE component = ?', ('test_component',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 'test_component')
        self.assertEqual(result[2], 'healthy')
    
    def test_create_incident(self):
        """Test incident creation"""
        self.monitor._create_incident('test_component', 'critical', 'Test error')
        
        conn = sqlite3.connect(self.monitor.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM incidents WHERE component = ?', ('test_component',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 'test_component')
        self.assertEqual(result[2], 'critical')
        self.assertEqual(result[4], 0)  # Not resolved
    
    def test_resolve_incident(self):
        """Test incident resolution"""
        # Create an incident first
        self.monitor._create_incident('test_component', 'critical', 'Test error')
        
        # Resolve it
        self.monitor.resolve_incident('test_component')
        
        conn = sqlite3.connect(self.monitor.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT resolved FROM incidents WHERE component = ?', ('test_component',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertEqual(result[0], 1)  # Resolved
    
    def test_record_metric(self):
        """Test metric recording"""
        self.monitor.record_metric('test_metric', 42.5)
        
        conn = sqlite3.connect(self.monitor.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM metrics WHERE metric_name = ?', ('test_metric',))
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 'test_metric')
        self.assertEqual(result[2], 42.5)
    
    def test_get_health_summary(self):
        """Test health summary generation"""
        # Log some health checks
        self.monitor._log_health_check('component1', 'healthy', 'OK', 100)
        self.monitor._log_health_check('component2', 'unhealthy', 'Error', 200)
        
        summary = self.monitor.get_health_summary()
        
        self.assertIn('recent_checks', summary)
        self.assertIn('active_incidents', summary)
        self.assertIn('overall_status', summary)
    
    def test_cleanup_old_records(self):
        """Test cleanup of old records"""
        # This test would require mocking time, for now just ensure it doesn't error
        try:
            self.monitor.cleanup_old_records(days=7)
        except Exception as e:
            self.fail(f"cleanup_old_records raised {e}")


class TestSelfHealingSystem(unittest.TestCase):
    """Test suite for self-healing system"""
    
    def setUp(self):
        self.monitor = HealthMonitor(db_path=':memory:')
        self.healing = SelfHealingSystem(self.monitor)
    
    def test_initialization(self):
        """Test self-healing system initializes"""
        self.assertIsNotNone(self.healing.monitor)
        self.assertEqual(self.healing.max_attempts, 3)
    
    def test_attempt_recovery_success(self):
        """Test successful recovery attempt"""
        recovery_func = Mock(return_value=True)
        
        result = self.healing.attempt_recovery('test_component', recovery_func)
        
        self.assertTrue(result)
        self.assertEqual(self.healing.recovery_attempts.get('test_component'), 0)
    
    def test_attempt_recovery_failure(self):
        """Test failed recovery attempt"""
        recovery_func = Mock(return_value=False)
        
        result = self.healing.attempt_recovery('test_component', recovery_func)
        
        self.assertFalse(result)
        self.assertEqual(self.healing.recovery_attempts.get('test_component'), 1)
    
    def test_attempt_recovery_max_attempts(self):
        """Test max attempts limit"""
        recovery_func = Mock(return_value=False)
        
        # Attempt 4 times (max is 3)
        for _ in range(4):
            self.healing.attempt_recovery('test_component', recovery_func)
        
        # Should not attempt on 4th try
        recovery_func.assert_called_times(3)
    
    def test_check_disk_space(self):
        """Test disk space check"""
        result = self.healing.check_disk_space()
        
        self.assertIn('success', result)
        self.assertIn('free_gb', result)


if __name__ == '__main__':
    unittest.main()
