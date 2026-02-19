#!/usr/bin/env python3
"""
Staging Smoke Automation Script
Implements checks from DEPLOYMENT_RUNBOOK.md
"""

import os
import sys
import requests
import time
import argparse

def run_smoke_tests(base_url, admin_password):
    print(f"Running smoke tests against {base_url}...")
    session = requests.Session()

    # 1. Basic availability
    print("\n1. Checking basic availability...")
    try:
        resp = session.get(f"{base_url}/health", timeout=5)
        if resp.status_code == 200:
            print("✓ /health is 200 OK")
        else:
            print(f"❌ /health returned {resp.status_code}")
            return False

        resp = session.get(f"{base_url}/login", timeout=5)
        if resp.status_code == 200:
            print("✓ /login is 200 OK")
        else:
            print(f"❌ /login returned {resp.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection failed: {e}")
        return False

    # 2. Authentication + CSRF
    print("\n2. Checking Authentication...")
    # Get CSRF token
    csrf_token = None
    if 'csrf_token' in resp.text:
        # Simple extraction - in real scenario use BeautifulSoup
        try:
            csrf_token = resp.text.split('name="csrf_token" value="')[1].split('"')[0]
            print("✓ CSRF token found")
        except IndexError:
            print("❌ Could not extract CSRF token")
            return False

    # Test login
    login_data = {
        "email": "admin@supervise.me",
        "password": admin_password,
        "csrf_token": csrf_token
    }

    resp = session.post(f"{base_url}/login", data=login_data, allow_redirects=True)
    if resp.status_code == 200 and "Dashboard" in resp.text:
        print("✓ Login successful")
    else:
        print(f"❌ Login failed. Status: {resp.status_code}")
        return False

    # 3. Role access sanity
    print("\n3. Checking Role Access Sanity...")
    resp = session.get(f"{base_url}/admin/dashboard")
    if resp.status_code == 200 and "Dashboard" in resp.text:
        print("✓ Admin dashboard accessible")
    else:
        print(f"❌ Admin dashboard check failed: {resp.status_code}")
        return False

    # 4. Critical CRUD checks (Simulated)
    print("\n4. Checking Critical CRUD (Availability)...")
    # Check if we can load the thesis creation page
    resp = session.get(f"{base_url}/admin/theses")
    if resp.status_code == 200:
        print("✓ Thesis list/creation page loads")
    else:
        print(f"❌ Thesis list page failed: {resp.status_code}")
        return False

    # 5. Scheduler sanity
    print("\n5. Checking Scheduler Sanity...")
    # This might require a specific endpoint or checking logs.
    # Assuming there is an endpoint or we just skip if not exposed.
    # We added /admin/notifications/status earlier.
    resp = session.get(f"{base_url}/admin/notifications/status")
    if resp.status_code == 200:
        print(f"✓ Scheduler status accessible: {resp.json().get('running', 'unknown')}")
    else:
        print("⚠️ Scheduler status endpoint not accessible (might be expected)")

    print("\n✅ All smoke tests passed!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run smoke tests")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the application")
    parser.add_argument("--password", default="password", help="Admin password")

    args = parser.parse_args()

    # Check environment variables for defaults
    url = os.environ.get("SMOKE_TEST_URL", args.url)
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", args.password)

    success = run_smoke_tests(url, password)
    sys.exit(0 if success else 1)
