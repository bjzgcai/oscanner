# Repository Data Extraction Methods - Comparison

**Repository**: shuxueshuxue/ink-and-memory
**URL**: https://github.com/shuxueshuxue/ink-and-memory
**Date**: 2026-01-04

This document compares two different extraction approaches for the same repository.

## Overview

| Method | Directory | Size | Extraction Time | LLM Used |
|--------|-----------|------|-----------------|----------|
| **Comprehensive** | `ink-and-memory/` | 154 MB | ~10 min | ❌ No |
| **Moderate** | `ink-and-memory-moderate/` | 12 MB | ~5 min | ❌ No |

## Method 1: Comprehensive (Full Repository Context)

**Directory**: [data/shuxueshuxue/ink-and-memory/](data/shuxueshuxue/ink-and-memory/)

### What It Includes
- ✅ Full git repository clone
- ✅ All 264 commits with complete history
- ✅ Complete file snapshots at each commit (in `commits/<sha>/files/`)
- ✅ Full diffs for all commits
- ✅ Repository structure
- ✅ Pull requests list
- ✅ Fully offline after download

### Data Size & Structure
```
154 MB total
├── repo/                  # Full git clone
├── commits/               # 264 commit directories
│   └── <sha>/
│       ├── <sha>.json    # Metadata
│       ├── <sha>.diff    # Git diff
│       └── files/        # Full file snapshots at this commit
├── commits_index.json
├── repo_info.json
├── repo_structure.json
└── pulls.json
```

### Extraction Method
- Tool: `tools/extract_repo_data.py`
- Approach: Git clone + `git show` for each commit
- API Calls: 0 (pure git operations)
- Requires: Git installed, network for clone only

### Best For
- Deep historical analysis
- Understanding code evolution
- Tracking file changes over time
- Complete offline analysis
- Academic research
- Forensic code analysis

### Advantages
- Complete repository history
- No API rate limits
- Fully offline capable
- File contents at every commit
- Can rebuild entire history

### Disadvantages
- Large storage (154 MB)
- Longer extraction time
- Includes entire repo clone
- May have redundant data

---

## Method 2: Moderate (Diff + File Context)

**Directory**: [data/shuxueshuxue/ink-and-memory-moderate/](data/shuxueshuxue/ink-and-memory-moderate/)

### What It Includes
- ✅ All 263 commits with diffs
- ✅ Commit metadata from GitHub API
- ✅ Current file contents (top 100 most-changed)
- ✅ Repository structure and tree
- ✅ File statistics
- ❌ NOT full git clone
- ❌ NOT historical file snapshots

### Data Size & Structure
```
12 MB total
├── commits/              # 263 commits
│   ├── <sha>.json       # Full API metadata
│   └── <sha>.diff       # Combined diff
├── files/               # Current file contents (48 fetched)
│   ├── <filepath>       # File content
│   └── <filepath>.json  # File metadata
├── commits_index.json   # 91 KB
├── commits_list.json    # 633 KB
├── repo_info.json
├── repo_tree.json
└── EXTRACTION_INFO.json
```

### Extraction Method
- Tool: `tools/extract_repo_data_moderate.py`
- Approach: GitHub API calls
- API Calls: ~600 requests
- Requires: GitHub token (for higher rate limits)

### Best For
- Quick code analysis
- LLM-based evaluation
- Commit pattern analysis
- Code review and quality assessment
- Bandwidth-constrained environments
- CI/CD integration

### Advantages
- 12x smaller (12 MB vs 154 MB)
- Faster extraction
- Focused on essential data
- Lower bandwidth usage
- API-based (no git needed)

### Disadvantages
- Requires GitHub token
- API rate limits (60/hr without token)
- No historical file snapshots
- Some files missing (deleted/renamed)
- Partially offline (missing full history)

---

## Detailed Comparison

### Size Efficiency
```
Comprehensive: 154 MB
Moderate:       12 MB
Ratio:          12.8x smaller
```

### Commits Coverage
```
Comprehensive: 264 commits (git log --all)
Moderate:      263 commits (API)
Difference:    1 commit (likely merge/branch difference)
```

### File Contents
```
Comprehensive: All files at every commit (~100,000+ file snapshots)
Moderate:      48 current files + diffs

Files mentioned in commits:
- Comprehensive: All historical versions
- Moderate:      151 unique paths, 48 current contents fetched
```

### Extraction Speed
```
Comprehensive: ~10 minutes (clone + process all commits)
Moderate:      ~5 minutes (API requests + file downloads)
```

### Offline Capability
```
Comprehensive: ✅ Fully offline after initial clone
Moderate:      ⚠️  Partial (diffs yes, full context needs API)
```

### API Usage
```
Comprehensive: 0 API calls (pure git)
Moderate:      ~600 API calls (263 commits + 100 file contents + metadata)
```

---

## Use Case Recommendations

### Choose Comprehensive When:
- 📊 Need complete historical context
- 🔍 Performing forensic analysis
- 📚 Academic or research purposes
- 🌐 Working offline after initial setup
- 🔄 Need to reconstruct repository at any point
- 🎯 Analyzing code evolution patterns
- 💾 Storage is not a constraint

### Choose Moderate When:
- ⚡ Need quick insights
- 🤖 LLM-based code evaluation
- 📈 Analyzing recent commit patterns
- 🔄 CI/CD integration
- 📱 Limited bandwidth environment
- 💰 API quota is available
- 🎯 Focus on code changes (diffs)
- 💾 Storage is limited

---

## Data Quality

Both methods provide:
- ✅ Complete commit metadata
- ✅ Full diffs for all commits
- ✅ Repository information
- ✅ Structured, parseable data
- ✅ No LLM preprocessing

### Integrity
```
Comprehensive: ⭐⭐⭐⭐⭐ (Complete git history)
Moderate:      ⭐⭐⭐⭐☆ (API data, some files missing)
```

### Completeness
```
Comprehensive: ⭐⭐⭐⭐⭐ (Everything from git)
Moderate:      ⭐⭐⭐⭐☆ (All commits, partial files)
```

### Efficiency
```
Comprehensive: ⭐⭐⭐☆☆ (Large but complete)
Moderate:      ⭐⭐⭐⭐⭐ (Optimized for analysis)
```

---

## Cost Analysis

### Storage Cost
```
Comprehensive: 154 MB × $0.023/GB/month = $0.0035/month
Moderate:       12 MB × $0.023/GB/month = $0.0003/month
```

### API Cost
```
Comprehensive: $0 (no API calls)
Moderate:      ~600 calls (free with token, 5000/hour limit)
```

### Total Cost
```
Comprehensive: Minimal (storage only)
Moderate:      Minimal (free tier sufficient)
```

---

## Example Usage

### Comprehensive - Analyzing File Evolution
```bash
# See how a file changed over time
for commit in $(cat data/shuxueshuxue/ink-and-memory/commits_index.json | jq -r '.[].hash'); do
  if [ -f "data/shuxueshuxue/ink-and-memory/commits/$commit/files/backend/config.py" ]; then
    echo "=== Commit $commit ==="
    cat "data/shuxueshuxue/ink-and-memory/commits/$commit/files/backend/config.py"
  fi
done
```

### Moderate - Quick Commit Analysis
```bash
# Get all commits that modified backend
cat data/shuxueshuxue/ink-and-memory-moderate/commits_index.json | \
  jq '.[] | select(.files[] | contains("backend")) | {sha, message, author}'
```

---

## Recommendation

For **LLM-based code evaluation** (your use case):
- **Use Moderate** ✅
  - 12x smaller, faster to process
  - Diffs are primary input for LLM
  - Current file context is sufficient
  - Easier to chunk and send to LLM
  - Lower token usage

For **historical analysis or offline research**:
- **Use Comprehensive** ✅
  - Complete historical context
  - No API dependencies
  - Can track any file's evolution
  - Better for academic work

---

## Next Steps

Both extractions are complete and ready for analysis:

1. **For quick LLM evaluation**: Use `ink-and-memory-moderate/`
2. **For deep analysis**: Use `ink-and-memory/`
3. **For best of both**: Keep both (total 166 MB)

See individual extraction summaries:
- [Comprehensive Summary](shuxueshuxue/ink-and-memory/EXTRACTION_SUMMARY.md)
- [Moderate Summary](shuxueshuxue/ink-and-memory-moderate/EXTRACTION_SUMMARY.md)
