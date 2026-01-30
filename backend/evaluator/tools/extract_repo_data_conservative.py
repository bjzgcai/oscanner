#!/usr/bin/env python3
"""
Conservative repository data extraction (Diff-only)

Extracts:
- Commit metadata (author, date, message)
- Diffs for all commits
- Repository basic info
- Commit statistics

Does NOT include:
- File contents (neither current nor historical)
- Full repository clone
- Repository tree/structure details
- Pull requests

This is the minimal extraction - just what's needed to understand code changes.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path


def mkdir_p(path):
    os.makedirs(path, exist_ok=True)


def http_get(url, token=None):
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'repo-extractor/1.0'
    }
    if token:
        headers['Authorization'] = f'token {token}'

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode()
            return data, resp.getheaders()
    except urllib.error.HTTPError as e:
        print(f'HTTPError {e.code} {url}', file=sys.stderr)
        try:
            err = e.read().decode()
            print(err, file=sys.stderr)
        except Exception:
            pass
        return None, None


def fetch_paginated(url_template, token=None, max_items=0):
    """Fetch all pages of results"""
    results = []
    page = 1

    while True:
        url = url_template + ('&' if '?' in url_template else '?') + f'per_page=100&page={page}'
        data, headers = http_get(url, token)

        if data is None:
            break

        try:
            arr = json.loads(data)
        except json.JSONDecodeError:
            break

        if not isinstance(arr, list):
            results.append(arr)
            break

        if not arr:
            break

        results.extend(arr)

        if len(arr) < 100:
            break

        if max_items > 0 and len(results) >= max_items:
            results = results[:max_items]
            break

        page += 1

    return results


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='Extract conservative repository context (diffs only)')
    parser.add_argument('--repo-url', required=True, help='GitHub repository URL')
    parser.add_argument('--out', required=True, help='Output directory')
    parser.add_argument('--token', help='GitHub token (or set GITHUB_TOKEN env var)')
    parser.add_argument('--max-commits', type=int, default=0, help='Max commits (0=all)')
    args = parser.parse_args()

    # Get token from args or environment
    token = args.token or os.environ.get('GITHUB_TOKEN')

    repo_url = args.repo_url.rstrip('/')
    if not repo_url.startswith('https://github.com/'):
        print('Only GitHub URLs supported', file=sys.stderr)
        sys.exit(1)

    parts = repo_url.replace('https://github.com/', '').split('/')
    if len(parts) < 2:
        print('Invalid GitHub URL', file=sys.stderr)
        sys.exit(1)

    owner, repo = parts[0], parts[1].replace('.git', '')
    out_dir = Path(args.out)
    mkdir_p(out_dir)

    print(f'Extracting conservative context (diffs only) for {owner}/{repo}')
    print(f'Output directory: {out_dir}')

    # 1. Fetch repository info (minimal)
    print('\n[1/3] Fetching repository info...')
    repo_info_url = f'https://api.github.com/repos/{owner}/{repo}'
    repo_data, _ = http_get(repo_info_url, token)

    if repo_data is None:
        print('Failed to fetch repository info', file=sys.stderr)
        sys.exit(1)

    repo_info = json.loads(repo_data)

    # Save only essential repo info (stripped down)
    minimal_repo_info = {
        'name': repo_info.get('name'),
        'full_name': repo_info.get('full_name'),
        'owner': repo_info.get('owner', {}).get('login'),
        'description': repo_info.get('description'),
        'html_url': repo_info.get('html_url'),
        'language': repo_info.get('language'),
        'stargazers_count': repo_info.get('stargazers_count'),
        'forks_count': repo_info.get('forks_count'),
        'open_issues_count': repo_info.get('open_issues_count'),
        'default_branch': repo_info.get('default_branch'),
        'created_at': repo_info.get('created_at'),
        'updated_at': repo_info.get('updated_at'),
        'pushed_at': repo_info.get('pushed_at'),
        'size': repo_info.get('size'),
        'license': repo_info.get('license', {}).get('name') if repo_info.get('license') else None
    }

    save_json(out_dir / 'repo_info.json', minimal_repo_info)
    print(f'  ✓ Saved minimal repo info (stars: {minimal_repo_info.get("stargazers_count", 0)})')

    # 2. Fetch commits list
    print('\n[2/3] Fetching commits list...')
    commits_url = f'https://api.github.com/repos/{owner}/{repo}/commits'
    commits_list = fetch_paginated(commits_url, token, args.max_commits)

    print(f'  ✓ Found {len(commits_list)} commits')

    # 3. Fetch detailed commit data with diffs only
    print('\n[3/3] Fetching commit diffs (no file contents)...')
    commits_dir = out_dir / 'commits'
    mkdir_p(commits_dir)

    commits_index = []
    total_additions = 0
    total_deletions = 0
    files_changed_set = set()
    authors_set = set()

    for i, commit_summary in enumerate(commits_list):
        sha = commit_summary.get('sha')
        if not sha:
            continue

        print(f'  [{i+1}/{len(commits_list)}] {sha[:8]}... ', end='', flush=True)

        # Fetch detailed commit data
        commit_url = f'https://api.github.com/repos/{owner}/{repo}/commits/{sha}'
        commit_data, _ = http_get(commit_url, token)

        if commit_data is None:
            print('✗ Failed')
            continue

        commit_obj = json.loads(commit_data)

        # Extract minimal commit metadata (no file contents)
        commit_info = commit_obj.get('commit', {})
        author_info = commit_info.get('author', {})
        committer_info = commit_info.get('committer', {})
        stats = commit_obj.get('stats', {})

        authors_set.add(author_info.get('name', 'Unknown'))

        # Create minimal metadata
        minimal_commit = {
            'sha': sha,
            'message': commit_info.get('message', ''),
            'author': {
                'name': author_info.get('name'),
                'email': author_info.get('email'),
                'date': author_info.get('date')
            },
            'committer': {
                'name': committer_info.get('name'),
                'email': committer_info.get('email'),
                'date': committer_info.get('date')
            },
            'stats': {
                'total': stats.get('total', 0),
                'additions': stats.get('additions', 0),
                'deletions': stats.get('deletions', 0)
            },
            'files_count': len(commit_obj.get('files', [])),
            'parents': [p.get('sha') for p in commit_obj.get('parents', [])]
        }

        total_additions += stats.get('additions', 0)
        total_deletions += stats.get('deletions', 0)

        # Save minimal commit JSON
        save_json(commits_dir / f'{sha}.json', minimal_commit)

        # Extract and save ONLY diffs (no file content metadata)
        files = commit_obj.get('files', [])
        diff_parts = []

        for file_obj in files:
            filename = file_obj.get('filename', '')
            patch = file_obj.get('patch', '')

            if filename:
                files_changed_set.add(filename)

            if patch:
                # Minimal diff header
                status = file_obj.get('status', 'modified')
                additions = file_obj.get('additions', 0)
                deletions = file_obj.get('deletions', 0)

                header = f'*** {status.upper()}: {filename} (+{additions}/-{deletions}) ***\n'
                diff_parts.append(header + patch + '\n')

        combined_diff = '\n'.join(diff_parts)

        # Save diff only if there are changes
        if combined_diff.strip():
            with open(commits_dir / f'{sha}.diff', 'w', encoding='utf-8') as f:
                f.write(combined_diff)

        # Create minimal index entry
        commit_msg = minimal_commit['message'].split('\n')[0][:100]  # First line, truncated

        commits_index.append({
            'sha': sha,
            'message': commit_msg,
            'author': author_info.get('name', ''),
            'date': author_info.get('date', ''),
            'additions': stats.get('additions', 0),
            'deletions': stats.get('deletions', 0),
            'files_changed': len(files)
        })

        print(f'✓ ({len(files)} files, +{stats.get("additions", 0)}/-{stats.get("deletions", 0)})')

    save_json(out_dir / 'commits_index.json', commits_index)
    print(f'\n  ✓ Saved {len(commits_index)} commit diffs')

    # 4. Create statistics summary
    print('\n[Summary] Creating extraction statistics...')

    statistics = {
        'repository': f'{owner}/{repo}',
        'url': repo_url,
        'extraction_type': 'conservative',
        'description': 'Diff-only (minimal)',
        'extraction_date': commits_index[0]['date'] if commits_index else None,
        'stats': {
            'total_commits': len(commits_index),
            'total_authors': len(authors_set),
            'unique_files_changed': len(files_changed_set),
            'total_additions': total_additions,
            'total_deletions': total_deletions,
            'total_changes': total_additions + total_deletions,
            'avg_additions_per_commit': round(total_additions / len(commits_index)) if commits_index else 0,
            'avg_deletions_per_commit': round(total_deletions / len(commits_index)) if commits_index else 0
        },
        'authors': sorted(list(authors_set)),
        'structure': {
            'commits/': f'{len(commits_index)} commits (JSON metadata + diffs only)',
            'commits_index.json': 'Minimal index of all commits',
            'repo_info.json': 'Basic repository metadata',
            'statistics.json': 'This file - extraction statistics'
        },
        'what_is_included': [
            'Commit metadata (author, date, message, stats)',
            'Full diffs for all commits',
            'Basic repository information',
            'Commit statistics and summaries'
        ],
        'what_is_NOT_included': [
            'File contents (neither current nor historical)',
            'Repository clone',
            'Repository file tree/structure',
            'Pull requests',
            'Issues',
            'Full API objects'
        ]
    }

    save_json(out_dir / 'statistics.json', statistics)

    print('\n' + '='*60)
    print('✓ CONSERVATIVE EXTRACTION COMPLETE')
    print('='*60)
    print(f'  Repository: {owner}/{repo}')
    print(f'  Commits: {len(commits_index)}')
    print(f'  Authors: {len(authors_set)}')
    print(f'  Files changed: {len(files_changed_set)}')
    print(f'  Total changes: +{total_additions}/-{total_deletions}')
    print(f'  Output: {out_dir}')
    print(f'  Data included: Diffs only (no file contents)')
    print()


if __name__ == '__main__':
    main()
