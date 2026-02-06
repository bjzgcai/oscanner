#!/usr/bin/env python3
"""
Example: Using the run-all endpoint to test a repository

This demonstrates how to use the all-in-one /api/runner/run-all endpoint
to clone, explore, and test a repository in a single API call.
"""

import requests
import json
import sys


def run_all_tests(repo_url: str, api_base_url: str = "http://localhost:8000"):
    """
    Run complete repository analysis (clone + explore + test) in one call.

    Args:
        repo_url: Repository URL (GitHub or Gitee)
        api_base_url: Base URL of the evaluator API

    Returns:
        Dictionary with test results or None on error
    """
    endpoint = f"{api_base_url}/api/runner/run-all"

    print("=" * 80)
    print(f"Testing Repository: {repo_url}")
    print("=" * 80)
    print(f"\nCalling: {endpoint}")
    print("This will:")
    print("  1. Clone the repository")
    print("  2. Explore and generate REPO_OVERVIEW.md")
    print("  3. Run tests")
    print("  4. Return pass/fail results")
    print("\nPlease wait (this may take a few minutes)...\n")

    try:
        response = requests.post(
            endpoint,
            json={"repo_url": repo_url},
            timeout=600  # 10 minutes timeout
        )

        if response.status_code == 200:
            result = response.json()

            print("=" * 80)
            print("RESULTS")
            print("=" * 80)
            print(f"Repository: {result['repo_url']}")
            print(f"Last Commit SHA: {result['end_sha']}")
            print(f"Total Tests: {result['total']}")
            print(f"Passed: {result['passed']}")
            print(f"Failed: {result['failed']}")
            print(f"Score: {result['score']}/100")
            print(f"Report: {result['report_path']}")
            print("=" * 80)

            return result

        else:
            print(f"[Error] API returned status {response.status_code}")
            print(f"Details: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print("[Error] Cannot connect to API server")
        print(f"Make sure the server is running at {api_base_url}")
        return None

    except requests.exceptions.Timeout:
        print("[Error] Request timed out after 10 minutes")
        print("The repository might be too large or tests are taking too long")
        return None

    except Exception as e:
        print(f"[Error] Unexpected error: {str(e)}")
        return None


def main():
    """Main entry point"""
    # Example repository URLs
    examples = [
        "https://gitee.com/zgcai/eval_test_1",
        "https://github.com/your-org/your-repo",
    ]

    if len(sys.argv) > 1:
        # Use provided repo URL
        repo_url = sys.argv[1]
    else:
        # Use first example
        repo_url = examples[0]
        print(f"No repo URL provided, using example: {repo_url}")
        print(f"Usage: {sys.argv[0]} <repo_url>\n")

    # Run the test
    result = run_all_tests(repo_url)

    if result:
        # Save result to file
        # Extract repo name from URL
        repo_name = result['repo_url'].rstrip('/').split('/')[-1].replace('.git', '')
        output_file = f"test_result_{repo_name}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\nFull result saved to: {output_file}")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
