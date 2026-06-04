#!/usr/bin/env python3
"""
Test script for /api/trajectory/analyze_one-off endpoint with start_sha and end_sha parameters.

This script demonstrates all corner cases:
1. Both start_sha and end_sha are None → all commits
2. Only start_sha provided → from start_sha to latest
3. Only end_sha provided → from first to end_sha
4. Both provided → from start_sha to end_sha (both inclusive)
5. start_sha not found → error
6. end_sha not found → error
7. start_sha newer than end_sha → error (invalid range)
8. start_sha == end_sha → single commit evaluation
9. No commits in range → empty result
10. Empty commit list → error
"""

import requests
import json
from typing import Optional

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "CarterWu"
REPO_URL = "https://gitee.com/zgcai/oscanner"
EMAILS = ["carter@example.com", "carter@work.com"]

# You'll need to replace these with actual commit SHAs from your repo
# These are just examples - you need to fetch real commits first
EXAMPLE_OLDEST_SHA = "first_commit_sha"  # Replace with actual oldest commit
EXAMPLE_MIDDLE_SHA = "middle_commit_sha"  # Replace with actual middle commit
EXAMPLE_NEWEST_SHA = "newest_commit_sha"  # Replace with actual newest commit
INVALID_SHA = "0000000000000000000000000000000000000000"


def test_analyze_one_off(
    username: str,
    repo_url: str,
    emails: list,
    start_sha: Optional[str] = None,
    end_sha: Optional[str] = None,
    test_name: str = "Test"
):
    """Test the analyze_one-off endpoint with given parameters."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Parameters:")
    print(f"  - username: {username}")
    print(f"  - repo_url: {repo_url}")
    print(f"  - emails: {emails}")
    print(f"  - start_sha: {start_sha or 'None (from first commit)'}")
    print(f"  - end_sha: {end_sha or 'None (to latest commit)'}")
    print(f"{'-'*80}")

    # Build query parameters
    params = {
        "plugin": "zgc_ai_native_2026",
        "checkpoint_strategy": "none"
    }

    if start_sha:
        params["start_sha"] = start_sha
    if end_sha:
        params["end_sha"] = end_sha

    # Build request body
    body = {
        "username": username,
        "repo_urls": [repo_url],
        "emails": emails
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/trajectory/analyze_one-off",
            params=params,
            json=body,
            timeout=300
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Success: {data.get('success', False)}")
            print(f"  Message: {data.get('message', 'N/A')}")
            print(f"  Commits analyzed: {data.get('commits_analyzed', 0)}")

            if data.get('checkpoint'):
                checkpoint = data['checkpoint']
                commits_range = checkpoint.get('commits_range', {})
                print(f"  Commit range:")
                print(f"    - Start SHA: {commits_range.get('start_sha', 'N/A')[:8]}...")
                print(f"    - End SHA: {commits_range.get('end_sha', 'N/A')[:8]}...")
                print(f"    - Count: {commits_range.get('commit_count', 0)}")
        else:
            print(f"✗ HTTP Error {response.status_code}")
            print(f"  Response: {response.text}")

    except requests.exceptions.Timeout:
        print(f"✗ Request timeout (300s)")
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")


def fetch_sample_commits():
    """Fetch some sample commits to use in tests."""
    print(f"\n{'='*80}")
    print("FETCHING SAMPLE COMMITS")
    print(f"{'='*80}")

    # First ensure data is extracted
    print("Extracting repository data...")
    params = {"platform": "gitee", "owner": "zgcai", "repo": "oscanner"}

    try:
        response = requests.post(
            f"{BASE_URL}/api/extract",
            params=params,
            timeout=60
        )

        if response.status_code == 200:
            print("✓ Repository data extracted successfully")
        else:
            print(f"✗ Failed to extract data: {response.text}")
            return None

    except Exception as e:
        print(f"✗ Failed to extract: {e}")
        return None

    # Now fetch commits (you would need an endpoint for this, or read from local data)
    # For now, return placeholder values
    print("\n⚠ Note: You need to manually replace the commit SHAs in this script")
    print("  with actual commit hashes from your repository.")
    return None


def run_all_tests():
    """Run all corner case tests."""
    print("\n" + "="*80)
    print("TRAJECTORY ANALYZE ONE-OFF: SHA RANGE CORNER CASES TEST SUITE")
    print("="*80)

    # First, try to fetch sample commits
    fetch_sample_commits()

    print("\n⚠ IMPORTANT: Before running these tests, you need to:")
    print("  1. Ensure the evaluator service is running (port 8000)")
    print("  2. Configure LLM API keys (OPENAI_API_KEY or OPEN_ROUTER_KEY)")
    print("  3. Update the commit SHA constants at the top of this script")
    print("  4. Optionally adjust USERNAME, REPO_URL, and EMAILS")

    print("\n" + "="*80)
    print("CORNER CASE TESTS")
    print("="*80)

    # Test 1: Both None - all commits
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=None,
        end_sha=None,
        test_name="Case 1: Both start_sha and end_sha are None (all commits)"
    )

    # Test 2: Only start_sha
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=EXAMPLE_MIDDLE_SHA,
        end_sha=None,
        test_name="Case 2: Only start_sha provided (from start_sha to latest)"
    )

    # Test 3: Only end_sha
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=None,
        end_sha=EXAMPLE_MIDDLE_SHA,
        test_name="Case 3: Only end_sha provided (from first to end_sha)"
    )

    # Test 4: Both provided (valid range)
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=EXAMPLE_OLDEST_SHA,
        end_sha=EXAMPLE_NEWEST_SHA,
        test_name="Case 4: Both provided (valid range, oldest to newest)"
    )

    # Test 5: start_sha not found
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=INVALID_SHA,
        end_sha=None,
        test_name="Case 5: start_sha not found (should error)"
    )

    # Test 6: end_sha not found
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=None,
        end_sha=INVALID_SHA,
        test_name="Case 6: end_sha not found (should error)"
    )

    # Test 7: start_sha newer than end_sha (invalid range)
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=EXAMPLE_NEWEST_SHA,
        end_sha=EXAMPLE_OLDEST_SHA,
        test_name="Case 7: start_sha newer than end_sha (should error - invalid range)"
    )

    # Test 8: start_sha == end_sha (single commit)
    test_analyze_one_off(
        username=USERNAME,
        repo_url=REPO_URL,
        emails=EMAILS,
        start_sha=EXAMPLE_MIDDLE_SHA,
        end_sha=EXAMPLE_MIDDLE_SHA,
        test_name="Case 8: start_sha == end_sha (single commit evaluation)"
    )

    print("\n" + "="*80)
    print("TEST SUITE COMPLETED")
    print("="*80)
    print("\nNotes:")
    print("- Cases 9 (no commits in range) and 10 (empty commit list) are")
    print("  implicitly tested based on the data in your repository")
    print("- Replace the example SHA constants with real values to run actual tests")


if __name__ == "__main__":
    run_all_tests()
