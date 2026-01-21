#!/usr/bin/env python3
"""
Moderate repository data extraction (Diff + File Context)

Extracts:
- Commit metadata
- Diffs for all commits
- Relevant file context (files mentioned in diffs)
- Repository info and structure

Does NOT include:
- Full repository clone
- Complete file snapshots at each commit (only current/relevant versions)
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
    parser = argparse.ArgumentParser(description='Extract moderate repository context (diffs + file context)')
    parser.add_argument('--repo-url', required=True, help='GitHub repository URL')
    parser.add_argument('--out', required=True, help='Output directory')
    parser.add_argument('--token', help='GitHub token (or set GITHUB_TOKEN env var)')
    parser.add_argument('--max-commits', type=int, default=500, help='Max commits (0=all, recommended: 300-500)')
    parser.add_argument('--platform', default='github', help='Platform (github, gitee, gitlab) - default: github')
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

    print(f'Extracting moderate context for {owner}/{repo}')
    print(f'Output directory: {out_dir}')

    # 1. Fetch repository info
    print('\n[1/5] Fetching repository info...')
    repo_info_url = f'https://api.github.com/repos/{owner}/{repo}'
    repo_data, _ = http_get(repo_info_url, token)

    if repo_data is None:
        print('Failed to fetch repository info', file=sys.stderr)
        sys.exit(1)

    repo_info = json.loads(repo_data)
    # Add platform info to repo_info
    repo_info['platform'] = args.platform
    save_json(out_dir / 'repo_info.json', repo_info)
    print(f'  ✓ Saved repo info (stars: {repo_info.get("stargazers_count", 0)}, platform: {args.platform})')

    default_branch = repo_info.get('default_branch', 'main')

    # 2. Fetch repository tree structure
    print('\n[2/5] Fetching repository structure...')
    tree_url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1'
    tree_data, _ = http_get(tree_url, token)

    if tree_data:
        tree_obj = json.loads(tree_data)
        save_json(out_dir / 'repo_tree.json', tree_obj)
        tree_count = len(tree_obj.get('tree', []))
        print(f'  ✓ Saved repository tree ({tree_count} items)')
    else:
        print('  ⚠ Could not fetch repository tree')

    # 3. Fetch commits list
    print('\n[3/5] Fetching commits list...')
    commits_url = f'https://api.github.com/repos/{owner}/{repo}/commits'
    commits_list = fetch_paginated(commits_url, token, args.max_commits)

    print(f'  ✓ Found {len(commits_list)} commits')
    save_json(out_dir / 'commits_list.json', commits_list)

    # 4. Fetch detailed commit data with diffs
    print('\n[4/5] Fetching commit details with diffs...')
    commits_dir = out_dir / 'commits'
    mkdir_p(commits_dir)

    commits_index = []
    files_context = {}  # Track unique files mentioned

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

        # Save commit JSON (includes files and patches)
        save_json(commits_dir / f'{sha}.json', commit_obj)

        # Extract and save combined diff
        files = commit_obj.get('files', [])
        diff_parts = []

        for file_obj in files:
            filename = file_obj.get('filename', '')
            patch = file_obj.get('patch', '')

            # Track files for context extraction
            if filename:
                files_context[filename] = files_context.get(filename, 0) + 1

            if patch:
                header = f'*** FILE: {filename} ***\n'
                diff_parts.append(header + patch + '\n')

        combined_diff = '\n'.join(diff_parts)
        with open(commits_dir / f'{sha}.diff', 'w', encoding='utf-8') as f:
            f.write(combined_diff)

        # Create index entry
        commit_msg = commit_obj.get('commit', {}).get('message', '')
        file_list = [f.get('filename') for f in files if f.get('filename')]

        commits_index.append({
            'sha': sha,
            'message': commit_msg.split('\n')[0][:100],  # First line, truncated
            'author': commit_obj.get('commit', {}).get('author', {}).get('name', ''),
            'date': commit_obj.get('commit', {}).get('author', {}).get('date', ''),
            'files_changed': len(file_list),
            'files': file_list
        })

        print(f'✓ ({len(file_list)} files)')

    save_json(out_dir / 'commits_index.json', commits_index)
    print(f'\n  ✓ Saved {len(commits_index)} commit details')

    # 5. Fetch current file contents for files mentioned in diffs
    print(f'\n[5/5] Fetching file context for {len(files_context)} unique files...')
    files_dir = out_dir / 'files'
    mkdir_p(files_dir)

    files_fetched = 0
    for i, (filepath, mention_count) in enumerate(sorted(files_context.items(), key=lambda x: -x[1])[:100]):  # Top 100 most changed
        print(f'  [{i+1}/{min(len(files_context), 100)}] {filepath}... ', end='', flush=True)

        # Fetch current file content
        file_url = f'https://api.github.com/repos/{owner}/{repo}/contents/{filepath}'
        file_data, _ = http_get(file_url, token)

        if file_data is None:
            print('✗')
            continue

        try:
            file_obj = json.loads(file_data)

            # Create directory structure
            file_path = files_dir / filepath
            mkdir_p(file_path.parent)

            # Save file metadata
            save_json(files_dir / f'{filepath}.json', {
                'path': filepath,
                'sha': file_obj.get('sha'),
                'size': file_obj.get('size'),
                'mentions': mention_count,
                'download_url': file_obj.get('download_url')
            })

            # Download actual file content if available
            download_url = file_obj.get('download_url')
            if download_url:
                content_data, _ = http_get(download_url, token)
                if content_data:
                    with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
                        f.write(content_data)
                    files_fetched += 1
                    print(f'✓ ({file_obj.get("size", 0)} bytes)')
                else:
                    print('✗ content')
            else:
                print('✗ no URL')

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f'✗ {e}')
            continue

    print(f'\n  ✓ Fetched {files_fetched} file contents')

    # 6. Create summary
    print('\n[Summary] Creating extraction summary...')
    summary = {
        'repository': f'{owner}/{repo}',
        'url': repo_url,
        'extraction_type': 'moderate',
        'description': 'Diffs + File Context',
        'stats': {
            'total_commits': len(commits_index),
            'unique_files_mentioned': len(files_context),
            'file_contents_fetched': files_fetched,
            'repository_info': 'included',
            'repository_tree': 'included' if tree_data else 'not available'
        },
        'structure': {
            'commits/': f'{len(commits_index)} commits with JSON metadata and diffs',
            'files/': f'{files_fetched} current file contents',
            'commits_index.json': 'Index of all commits',
            'commits_list.json': 'API commits list',
            'repo_info.json': 'Repository metadata',
            'repo_tree.json': 'Repository file tree'
        }
    }

    save_json(out_dir / 'EXTRACTION_INFO.json', summary)

    # Create initial sync_state.json for incremental sync
    if commits_index:
        from datetime import datetime
        first_commit = commits_index[0]
        sync_state = {
            "last_synced_at": datetime.now().isoformat(),
            "last_commit_sha": first_commit.get("sha") or first_commit.get("hash"),
            "last_commit_date": first_commit.get("date", ""),
            "total_commits_fetched": len(commits_index),
            "sync_history": [{
                "synced_at": datetime.now().isoformat(),
                "commits_added": len(commits_index),
                "last_sha": first_commit.get("sha") or first_commit.get("hash"),
                "mode": "initial_extraction"
            }]
        }
        save_json(out_dir / 'sync_state.json', sync_state)
        print(f"✓ Created sync_state.json (last commit: {first_commit.get('sha', first_commit.get('hash', ''))[:8]})")

    print('\n' + '='*60)
    print('✓ MODERATE EXTRACTION COMPLETE')
    print('='*60)
    print(f'  Repository: {owner}/{repo}')
    print(f'  Commits: {len(commits_index)}')
    print(f'  Files context: {files_fetched} fetched, {len(files_context)} mentioned')
    print(f'  Output: {out_dir}')
    print()


if __name__ == '__main__':
    main()
