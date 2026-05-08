#!/usr/bin/env python3
"""
Test runner for the automation system
"""

import unittest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import test modules
from tests import test_image_scraper
from tests import test_facebook_poster
from tests import test_health_monitor
from tests import test_analytics


def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test modules
    suite.addTests(loader.loadTestsFromModule(test_image_scraper))
    suite.addTests(loader.loadTestsFromModule(test_facebook_poster))
    suite.addTests(loader.loadTestsFromModule(test_health_monitor))
    suite.addTests(loader.loadTestsFromModule(test_analytics))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*70)
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())
