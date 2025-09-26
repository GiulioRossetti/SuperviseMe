#!/usr/bin/env python3
"""
SuperviseMe Application Functionality Test

This script tests the basic functionality of the SuperviseMe application
to ensure the database recreation was successful and the app works correctly.
"""

import os
import sys
import time
import requests
import threading
from multiprocessing import Process

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from superviseme import create_app


def start_test_server(port=8082):
    """Start the Flask application in test mode"""
    app = create_app(db_type="sqlite")
    app.run(host="localhost", port=port, debug=False)


def test_application_endpoints():
    """Test basic application endpoints"""
    
    base_url = "http://localhost:8082"
    
    print("Testing application functionality...")
    
    # Give the server time to start
    time.sleep(2)
    
    # Test basic endpoints
    test_cases = [
        {
            "endpoint": "/",
            "description": "Root endpoint (should redirect to login)",
            "expected_status": [200, 302]  # Should redirect to login
        },
        {
            "endpoint": "/login",
            "description": "Login page", 
            "expected_status": [200]
        },
        {
            "endpoint": "/health",
            "description": "Health check endpoint",
            "expected_status": [200]
        }
    ]
    
    results = []
    
    for test in test_cases:
        try:
            url = f"{base_url}{test['endpoint']}"
            response = requests.get(url, timeout=10)
            
            success = response.status_code in test['expected_status']
            results.append({
                "test": test['description'],
                "url": url,
                "status_code": response.status_code,
                "success": success
            })
            
            if success:
                print(f"✓ {test['description']}: {response.status_code}")
            else:
                print(f"❌ {test['description']}: {response.status_code} (expected one of {test['expected_status']})")
                
        except requests.exceptions.RequestException as e:
            results.append({
                "test": test['description'],
                "url": url,
                "error": str(e),
                "success": False
            })
            print(f"❌ {test['description']}: Error - {e}")
    
    return results


def test_database_queries():
    """Test basic database queries"""
    
    print("\nTesting database queries...")
    
    try:
        app = create_app(db_type="sqlite")
        
        with app.app_context():
            from superviseme.models import User_mgmt, Thesis, Notification
            
            # Test user query
            admin_user = User_mgmt.query.filter_by(username='admin').first()
            if admin_user:
                print(f"✓ Admin user found: {admin_user.username} ({admin_user.email})")
            else:
                print("❌ Admin user not found")
                return False
            
            # Test table counts
            user_count = User_mgmt.query.count()
            thesis_count = Thesis.query.count()
            notification_count = Notification.query.count()
            
            print(f"✓ Database queries successful:")
            print(f"  - Users: {user_count}")
            print(f"  - Theses: {thesis_count}")
            print(f"  - Notifications: {notification_count}")
            
            return True
            
    except Exception as e:
        print(f"❌ Database query error: {e}")
        return False


def main():
    """Main test function"""
    
    print("SuperviseMe Application Functionality Test")
    print("=" * 50)
    
    # Test database queries first
    db_success = test_database_queries()
    
    if not db_success:
        print("\n❌ Database tests failed. Cannot proceed with web tests.")
        return 1
    
    # Start the application server in a separate process
    print(f"\nStarting test server...")
    server_process = Process(target=start_test_server, args=(8082,))
    server_process.start()
    
    try:
        # Test web endpoints
        web_results = test_application_endpoints()
        
        # Summary
        successful_tests = sum(1 for result in web_results if result.get('success', False))
        total_tests = len(web_results)
        
        print(f"\n{'=' * 50}")
        print(f"Test Results:")
        print(f"✓ Database tests: {'PASSED' if db_success else 'FAILED'}")
        print(f"✓ Web endpoint tests: {successful_tests}/{total_tests} passed")
        
        if db_success and successful_tests == total_tests:
            print(f"\n🎉 All tests passed! The application is working correctly.")
            return 0
        else:
            print(f"\n⚠️  Some tests failed. Check the output above for details.")
            return 1
            
    finally:
        # Clean up: terminate the server process
        server_process.terminate()
        server_process.join(timeout=5)
        if server_process.is_alive():
            server_process.kill()


if __name__ == "__main__":
    sys.exit(main())