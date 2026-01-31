#!/usr/bin/env python3
import os
import sys
import json
import argparse
import subprocess
import urllib.request
import urllib.error


def run(cmd, cwd=None):
    p = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr


def mkdir_p(path):
    os.makedirs(path, exist_ok=True)


def fetch_pulls(owner, repo, out_path):
    pulls = []
    page = 1
    while True:
        url = f'https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=100&page={page}'
        try:
            with urllib.request.urlopen(url) as resp:
                data = resp.read().decode()
        except urllib.error.HTTPError as e:
            print('HTTPError fetching PRs:', e, file=sys.stderr)
            break
        page_data = json.loads(data)
        if not page_data:
            break
        pulls.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1
    with open(out_path, 'w') as f:
        json.dump(pulls, f, indent=2)
    print(f'Wrote {len(pulls)} pulls to {out_path}')


def save_repo_structure(repo_path, out_path):
    tree = []
    for root, dirs, files in os.walk(repo_path):
        rel = os.path.relpath(root, repo_path)
        if rel == '.':
            rel = ''
        entry = {'path': rel, 'dirs': sorted(dirs), 'files': sorted(files)}
        tree.append(entry)
    with open(out_path, 'w') as f:
        json.dump(tree, f, indent=2)
    print('Saved repo structure to', out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-url', required=True, help='HTTPS repo URL')
    parser.add_argument('--out', required=True, help='Output directory to store data')
    parser.add_argument('--clone-dir', required=False, help='Where to clone the git repo (defaults to <out>/repo)')
    parser.add_argument('--max-commits', type=int, default=0, help='Max number of commits to process (0=all)')
    args = parser.parse_args()

    repo_url = args.repo_url.rstrip('/')
    out_dir = args.out
    mkdir_p(out_dir)
    clone_dir = args.clone_dir if args.clone_dir else os.path.join(out_dir, 'repo')

    # Clone if not exists
    if not os.path.isdir(clone_dir) or not os.path.isdir(os.path.join(clone_dir, '.git')):
        print('Cloning', repo_url, '->', clone_dir)
        rc, out, err = run(f'git clone {repo_url} {clone_dir}')
        if rc != 0:
            print('git clone failed', err, file=sys.stderr)
            sys.exit(1)
    else:
        print('Repo already present, fetching latest')
        rc, out, err = run('git fetch --all', cwd=clone_dir)
        if rc != 0:
            print('git fetch failed', err, file=sys.stderr)

    # Determine owner/name
    parts = repo_url.replace('https://github.com/', '').split('/')
    if len(parts) < 2:
        print('Cannot parse repo owner/name from URL', repo_url, file=sys.stderr)
        sys.exit(1)
    owner, name = parts[0], parts[1]

    # Fetch pulls
    pulls_out = os.path.join(out_dir, 'pulls.json')
    fetch_pulls(owner, name, pulls_out)

    # Prepare commits output dirs
    commits_dir = os.path.join(out_dir, 'commits')
    mkdir_p(commits_dir)

    # List commits (all refs)
    rc, stdout, stderr = run('git rev-list --all', cwd=clone_dir)
    if rc != 0:
        print('git rev-list failed', stderr, file=sys.stderr)
        sys.exit(1)
    hashes = [h.strip() for h in stdout.splitlines() if h.strip()]
    if args.max_commits and args.max_commits > 0:
        hashes = hashes[:args.max_commits]
    print('Found', len(hashes), 'commits')

    commits_index = []
    for i, h in enumerate(hashes):
        print(f'Processing commit {i+1}/{len(hashes)}: {h}')
        commit_dir = os.path.join(commits_dir, h)
        mkdir_p(commit_dir)
        # Save diff
        diff_path = os.path.join(commit_dir, f'{h}.diff')
        rc, out, err = run(f'git show {h} --unified=3 --no-color', cwd=clone_dir)
        if rc != 0:
            print('git show failed for', h, err, file=sys.stderr)
            continue
        with open(diff_path, 'w') as f:
            f.write(out)
        # Get metadata
        rc, meta_out, meta_err = run(f'git show -s --format=%H%n%an%n%ae%n%ad%n%s {h}', cwd=clone_dir)
        meta_lines = meta_out.splitlines()
        meta = {
            'hash': meta_lines[0] if len(meta_lines) > 0 else h,
            'author': meta_lines[1] if len(meta_lines) > 1 else '',
            'email': meta_lines[2] if len(meta_lines) > 2 else '',
            'date': meta_lines[3] if len(meta_lines) > 3 else '',
            'subject': meta_lines[4] if len(meta_lines) > 4 else ''
        }
        # Files changed in commit
        rc, files_out, files_err = run(f'git diff-tree --no-commit-id --name-only -r {h}', cwd=clone_dir)
        files = [p.strip() for p in files_out.splitlines() if p.strip()]
        files_info = []
        for path in files:
            safe_path = path.replace('/', os.sep)
            # save file content at this commit
            try:
                rc, file_content, file_err = run(f'git show {h}:{path}', cwd=clone_dir)
                # create dir
                file_save_dir = os.path.join(commit_dir, 'files', os.path.dirname(path))
                if file_save_dir:
                    mkdir_p(file_save_dir)
                file_save_path = os.path.join(commit_dir, 'files', *path.split('/'))
                with open(file_save_path, 'w', encoding='utf-8', errors='ignore') as ff:
                    ff.write(file_content)
            except Exception as e:
                file_content = ''
            files_info.append({'path': path, 'file_saved': os.path.exists(os.path.join(commit_dir, 'files', *path.split('/')) )})
        meta['files'] = files
        meta['diff'] = os.path.relpath(diff_path, out_dir)
        # Related files: files changed together (same commit)
        meta['related_files'] = {p: [q for q in files if q != p] for p in files}
        # Save metadata
        with open(os.path.join(commit_dir, f'{h}.json'), 'w') as f:
            json.dump(meta, f, indent=2)
        commits_index.append({'hash': h, 'meta': os.path.relpath(os.path.join(commit_dir, f'{h}.json'), out_dir)})

    with open(os.path.join(out_dir, 'commits_index.json'), 'w') as f:
        json.dump(commits_index, f, indent=2)
    print('Wrote commits index with', len(commits_index), 'entries')

    # Save repo structure
    save_repo_structure(clone_dir, os.path.join(out_dir, 'repo_structure.json'))
    print('All done. Outputs in', out_dir)

if __name__ == '__main__':
    main()
