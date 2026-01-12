#!/usr/bin/env python3
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from urllib.parse import urlencode

HEADERS = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'repo-extractor/1.0'}


def mkdir_p(p):
    os.makedirs(p, exist_ok=True)


def http_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read().decode()
            headers = resp.getheaders()
            return data, headers
    except urllib.error.HTTPError as e:
        print('HTTPError', e.code, e.reason, url, file=sys.stderr)
        try:
            err = e.read().decode()
            print(err, file=sys.stderr)
        except Exception:
            pass
        return None, None


def fetch_all(url_template, out_list_key=None):
    results = []
    page = 1
    while True:
        url = url_template + ('&' if '?' in url_template else '?') + f'per_page=100&page={page}'
        data, headers = http_get(url)
        if data is None:
            break
        arr = json.loads(data)
        if not isinstance(arr, list):
            # if single object
            results.append(arr)
            break
        results.extend(arr)
        if len(arr) < 100:
            break
        page += 1
    return results


def save_json(path, obj):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-url', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--max-commits', type=int, default=0)
    args = parser.parse_args()

    repo_url = args.repo_url.rstrip('/')
    if not repo_url.startswith('https://github.com/'):
        print('Only github.com URLs supported', file=sys.stderr)
        sys.exit(1)
    parts = repo_url.replace('https://github.com/', '').split('/')
    owner, repo = parts[0], parts[1]

    out_dir = args.out
    mkdir_p(out_dir)

    # Repo info to get default branch
    repo_info_url = f'https://api.github.com/repos/{owner}/{repo}'
    repo_info_data, _ = http_get(repo_info_url)
    if repo_info_data is None:
        print('Failed to fetch repo info, aborting', file=sys.stderr)
        sys.exit(1)
    repo_info = json.loads(repo_info_data)
    save_json(os.path.join(out_dir, 'repo_info.json'), repo_info)
    default_branch = repo_info.get('default_branch', 'main')

    # Fetch pulls
    pulls_url = f'https://api.github.com/repos/{owner}/{repo}/pulls?state=all'
    pulls = fetch_all(pulls_url)
    mkdir_p(os.path.join(out_dir, 'pulls'))
    for pr in pulls:
        num = pr.get('number')
        if not num:
            continue
        pr_detail_url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{num}'
        pr_data, _ = http_get(pr_detail_url)
        if pr_data:
            pr_obj = json.loads(pr_data)
            save_json(os.path.join(out_dir, 'pulls', f'pr_{num}.json'), pr_obj)
        # files for PR
        pr_files_url = f'https://api.github.com/repos/{owner}/{repo}/pulls/{num}/files'
        files = fetch_all(pr_files_url)
        save_json(os.path.join(out_dir, 'pulls', f'pr_{num}_files.json'), files)
        # Save combined diff
        diff_combined = ''
        for fobj in files:
            patch = fobj.get('patch') or ''
            filename = fobj.get('filename')
            header = f'*** FILE: {filename} ***\n'
            diff_combined += header + patch + '\n\n'
        with open(os.path.join(out_dir, 'pulls', f'pr_{num}.diff'), 'w') as df:
            df.write(diff_combined)

    save_json(os.path.join(out_dir, 'pulls_index.json'), [ {'number': p.get('number'), 'title': p.get('title')} for p in pulls ])

    # Fetch commits list
    commits_url = f'https://api.github.com/repos/{owner}/{repo}/commits'
    commits = fetch_all(commits_url)
    mkdir_p(os.path.join(out_dir, 'commits'))
    if args.max_commits and args.max_commits > 0:
        commits = commits[:args.max_commits]
    commits_index = []
    for c in commits:
        sha = c.get('sha')
        if not sha:
            continue
        commit_detail_url = f'https://api.github.com/repos/{owner}/{repo}/commits/{sha}'
        data, _ = http_get(commit_detail_url)
        if data is None:
            continue
        obj = json.loads(data)
        # Save commit JSON (includes files and patches when available)
        save_json(os.path.join(out_dir, 'commits', f'{sha}.json'), obj)
        # Save combined diff
        files = obj.get('files', [])
        diff_combined = ''
        for fobj in files:
            patch = fobj.get('patch') or ''
            filename = fobj.get('filename')
            header = f'*** FILE: {filename} ***\n'
            diff_combined += header + patch + '\n\n'
        with open(os.path.join(out_dir, 'commits', f'{sha}.diff'), 'w') as df:
            df.write(diff_combined)
        # Save each file content if blob raw_url available (not always), skip large binaries
        file_entries = []
        for fobj in files:
            fn = fobj.get('filename')
            file_entries.append(fn)
        commits_index.append({'sha': sha, 'message': obj.get('commit',{}).get('message',''), 'files': file_entries})

    save_json(os.path.join(out_dir, 'commits_index.json'), commits_index)

    # Get repo tree for default branch
    tree_url = f'https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1'
    tree_data, _ = http_get(tree_url)
    if tree_data:
        tree_obj = json.loads(tree_data)
        save_json(os.path.join(out_dir, 'repo_tree.json'), tree_obj)

    print('API extraction completed. Outputs in', out_dir)

if __name__ == '__main__':
    main()
