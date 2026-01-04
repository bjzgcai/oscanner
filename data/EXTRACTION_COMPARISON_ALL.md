# Repository Data Extraction Methods - Complete Comparison

**Repository**: shuxueshuxue/ink-and-memory  
**URL**: https://github.com/shuxueshuxue/ink-and-memory  
**Date**: 2026-01-04

This document compares **three different extraction approaches** for the same repository.

## Overview

| Method | Directory | Size | Time | API Calls | LLM Used |
|--------|-----------|------|------|-----------|----------|
| **Conservative** | `ink-and-memory-conservative/` | **5.3 MB** | ~5 min | ~530 | ❌ No |
| **Moderate** | `ink-and-memory-moderate/` | **12 MB** | ~5 min | ~600 | ❌ No |
| **Comprehensive** | `ink-and-memory/` | **154 MB** | ~10 min | 0 | ❌ No |

## Quick Selection Guide

```
Need                     → Use This
─────────────────────────────────────────
Smallest size            → Conservative (5.3 MB)
Balanced approach        → Moderate (12 MB)
Complete history         → Comprehensive (154 MB)

Fastest analysis         → Conservative
Some file contents       → Moderate
Full offline work        → Comprehensive

LLM diff evaluation      → Conservative ⭐
LLM with context         → Moderate
Deep research            → Comprehensive
```

---

## Method 1: Conservative (Diff-only) ⚡

**Directory**: [data/shuxueshuxue/ink-and-memory-conservative/](data/shuxueshuxue/ink-and-memory-conservative/)

### What It Includes
- ✅ All 263 commits with full diffs
- ✅ Minimal commit metadata (author, date, message, stats)
- ✅ Basic repository information
- ✅ Commit statistics
- ❌ NO file contents at all
- ❌ NO repository clone
- ❌ NO repository structure

### Data Size & Structure
```
5.3 MB total (smallest)
├── commits/              # 263 commits
│   ├── <sha>.json       # Minimal metadata only
│   └── <sha>.diff       # Diff only
├── commits_index.json   # 67 KB
├── repo_info.json       # 549 bytes
└── statistics.json      # 1.3 KB
```

### Extraction Method
- **Tool**: `tools/extract_repo_data_conservative.py`
- **Approach**: GitHub API (minimal data)
- **API Calls**: ~530 requests
- **Speed**: ~5 minutes

### Best For
- ⚡ Pure diff analysis
- 🤖 LLM-based diff review
- 💾 Minimal storage scenarios
- 🚀 CI/CD integration
- 🌐 Bandwidth-constrained
- 💰 Token cost optimization

### Advantages
- **29x smaller** than comprehensive
- **2.3x smaller** than moderate
- Fastest processing
- Minimal bandwidth
- Lowest token usage
- Pure signal, no noise

### Disadvantages
- No file contents at all
- Cannot see current code
- No repository structure
- Limited to diff analysis only

---

## Method 2: Moderate (Diff + File Context) ⚖️

**Directory**: [data/shuxueshuxue/ink-and-memory-moderate/](data/shuxueshuxue/ink-and-memory-moderate/)

### What It Includes
- ✅ All 263 commits with diffs
- ✅ Full commit metadata from API
- ✅ Current file contents (48 files, top 100 prioritized)
- ✅ Repository tree structure
- ✅ File statistics
- ❌ NOT full git clone
- ❌ NOT historical file snapshots

### Data Size & Structure
```
12 MB total (balanced)
├── commits/              # 263 commits
│   ├── <sha>.json       # Full API metadata
│   └── <sha>.diff       # Combined diff
├── files/               # 48 current files
│   ├── <filepath>       # File content
│   └── <filepath>.json  # File metadata
├── commits_index.json   # 91 KB
├── commits_list.json    # 633 KB
├── repo_info.json
├── repo_tree.json
└── EXTRACTION_INFO.json
```

### Extraction Method
- **Tool**: `tools/extract_repo_data_moderate.py`
- **Approach**: GitHub API (selective files)
- **API Calls**: ~600 requests
- **Speed**: ~5 minutes

### Best For
- 🔍 Code analysis with context
- 🤖 LLM evaluation (balanced)
- 📊 Commit pattern analysis
- 🎯 Code review
- ⚖️ Balance size vs features
- 📝 Understanding architecture

### Advantages
- **12x smaller** than comprehensive
- Has some file context
- Current code state available
- Repository structure included
- Good balance

### Disadvantages
- Requires GitHub token
- API rate limits
- Only 48/151 files fetched
- No historical file snapshots
- Partially offline

---

## Method 3: Comprehensive (Full Repository Context) 📚

**Directory**: [data/shuxueshuxue/ink-and-memory/](data/shuxueshuxue/ink-and-memory/)

### What It Includes
- ✅ Full git repository clone
- ✅ All 264 commits
- ✅ Complete file snapshots at each commit
- ✅ Full diffs for all commits
- ✅ Repository structure
- ✅ Pull requests list
- ✅ Fully offline capable

### Data Size & Structure
```
154 MB total (complete)
├── repo/                  # Full git clone
├── commits/               # 264 commit directories
│   └── <sha>/
│       ├── <sha>.json    # Metadata
│       ├── <sha>.diff    # Git diff
│       └── files/        # Full file snapshots
├── commits_index.json
├── repo_info.json
├── repo_structure.json
└── pulls.json
```

### Extraction Method
- **Tool**: `tools/extract_repo_data.py`
- **Approach**: Git clone + git operations
- **API Calls**: 0 (pure git)
- **Speed**: ~10 minutes

### Best For
- 📚 Deep historical analysis
- 🔬 Code evolution study
- 🌐 Complete offline work
- 🎓 Academic research
- 🔍 Forensic analysis
- 📊 Full context analysis

### Advantages
- Complete repository history
- No API dependencies
- Fully offline capable
- File contents at every commit
- Can rebuild entire history
- No rate limits

### Disadvantages
- Large storage (154 MB)
- Longer extraction time
- Includes entire repo clone
- High LLM token usage
- May have redundant data

---

## Detailed Comparison Matrix

| Feature | Conservative | Moderate | Comprehensive |
|---------|-------------|----------|---------------|
| **Size** | 5.3 MB | 12 MB | 154 MB |
| **Relative** | 1x | 2.3x | 29x |
| **Commits** | 263 | 263 | 264 |
| **Diffs** | ✅ All | ✅ All | ✅ All |
| **File Contents** | ❌ None | 48 current | All historical |
| **Repo Clone** | ❌ No | ❌ No | ✅ Yes |
| **Repo Structure** | ❌ No | ✅ Basic | ✅ Complete |
| **Pull Requests** | ❌ No | ❌ No | ✅ Yes |
| **Extraction Time** | 5 min | 5 min | 10 min |
| **API Calls** | ~530 | ~600 | 0 |
| **Offline Use** | Partial | Partial | ✅ Full |
| **LLM Tokens** | ~1M | ~3M | ~10M |
| **Storage Cost/mo** | $0.0001 | $0.0003 | $0.0035 |
| **Best Use Case** | Diff analysis | Balanced | Research |

### Size Comparison Visualization
```
Conservative: █ 5.3 MB
Moderate:     ██▌ 12 MB (2.3x)
Comprehensive: ████████████████████████████▉ 154 MB (29x)
```

### API Usage Comparison
```
Conservative: ~530 API calls
Moderate:     ~600 API calls
Comprehensive: 0 API calls (pure git)
```

### Token Usage Estimate
```
Conservative: ~1M tokens   (LLM cost: $0.25-1.00)
Moderate:     ~3M tokens   (LLM cost: $0.75-3.00)
Comprehensive: ~10M tokens  (LLM cost: $2.50-10.00)
```

---

## Use Case Recommendations

### Choose Conservative When:
- ⚡ **Speed is critical**
- 💾 **Storage is very limited** (<10 MB)
- 🤖 **LLM diff review** is primary goal
- 📊 **Commit pattern analysis** only
- 🚀 **CI/CD integration**
- 🌐 **Low bandwidth environment**
- 💰 **Minimizing LLM token costs**
- 📈 **Quick insights** needed
- ✅ **Diffs are sufficient**

### Choose Moderate When:
- 🔍 **Need some file context**
- ⚖️ **Balancing size and features**
- 🤖 **LLM evaluation with context**
- 📝 **Code review** with examples
- 💾 **Storage is limited** (<50 MB)
- 🎯 **Most practical scenarios**
- 📊 **Understanding architecture**
- ✅ **Current code state** needed

### Choose Comprehensive When:
- 📚 **Need complete history**
- 🔬 **Code evolution study**
- 🌐 **Offline work** required
- 🎓 **Academic research**
- 🔍 **Forensic analysis**
- 💾 **Storage is not constrained**
- 📊 **Full context** essential
- ✅ **Complete repository** needed

---

## Task-Specific Recommendations

| Task | Conservative | Moderate | Comprehensive |
|------|-------------|----------|---------------|
| **Commit Pattern Analysis** | ⭐⭐⭐ Best | ⭐⭐ Good | ⭐ OK |
| **Code Review** | ⭐⭐⭐ Best | ⭐⭐⭐ Best | ⭐⭐ Good |
| **Architecture Study** | ❌ Cannot | ⭐⭐ Good | ⭐⭐⭐ Best |
| **Historical Research** | ❌ Cannot | ⭐ Limited | ⭐⭐⭐ Best |
| **Quick Insights** | ⭐⭐⭐ Best | ⭐⭐ Good | ⭐ Slow |
| **LLM Evaluation** | ⭐⭐⭐ Best | ⭐⭐ Good | ⭐ Costly |
| **Offline Analysis** | ⭐ Partial | ⭐ Partial | ⭐⭐⭐ Best |
| **CI/CD Integration** | ⭐⭐⭐ Best | ⭐⭐ Good | ⭐ Heavy |
| **Cost Efficiency** | ⭐⭐⭐ Best | ⭐⭐ Good | ⭐ OK |

---

## Cost Analysis

### Storage Costs (AWS S3 Standard)
```
Conservative:  5.3 MB × $0.023/GB/month = $0.0001/month
Moderate:      12 MB × $0.023/GB/month  = $0.0003/month
Comprehensive: 154 MB × $0.023/GB/month = $0.0035/month
```

### API Costs (GitHub)
```
Conservative:  ~530 calls (free tier: 5000/hour)
Moderate:      ~600 calls (free tier: 5000/hour)
Comprehensive: 0 calls (no API usage)
```

### LLM Token Costs (Estimated, Claude Sonnet 4.5)
```
Conservative:  ~1M tokens × $3/1M  = ~$3.00
Moderate:      ~3M tokens × $3/1M  = ~$9.00
Comprehensive: ~10M tokens × $3/1M = ~$30.00
```

### Total Cost Estimate
```
Conservative:  $3.00 (LLM) + $0.0001 (storage) = ~$3.00
Moderate:      $9.00 (LLM) + $0.0003 (storage) = ~$9.00
Comprehensive: $30.00 (LLM) + $0.0035 (storage) = ~$30.00
```

---

## Example Usage Scenarios

### Conservative - Quick Diff Analysis
```bash
# Find largest commits
cat data/shuxueshuxue/ink-and-memory-conservative/commits_index.json | \
  jq 'sort_by(.additions + .deletions) | reverse | .[0:10]'

# Analyze specific commit diff
cat data/shuxueshuxue/ink-and-memory-conservative/commits/<sha>.diff
```

### Moderate - Code Review with Context
```bash
# Get commits that modified backend with file context
cat data/shuxueshuxue/ink-and-memory-moderate/commits_index.json | \
  jq '.[] | select(.files[] | contains("backend"))'

# View current file content
cat data/shuxueshuxue/ink-and-memory-moderate/files/backend/server.py
```

### Comprehensive - Historical Analysis
```bash
# Track file evolution over time
for commit in $(cat data/shuxueshuxue/ink-and-memory/commits_index.json | jq -r '.[].hash'); do
  if [ -f "data/shuxueshuxue/ink-and-memory/commits/$commit/files/backend/config.py" ]; then
    echo "=== Commit $commit ==="
    cat "data/shuxueshuxue/ink-and-memory/commits/$commit/files/backend/config.py"
  fi
done
```

---

## Decision Tree

```
Start: What do you need?
│
├─ Only diffs/changes?
│  └─ Conservative (5.3 MB) ✅
│
├─ Diffs + some file contents?
│  └─ Moderate (12 MB) ✅
│
└─ Complete repository history?
   └─ Comprehensive (154 MB) ✅

Alternative decision path:

Storage limit?
├─ <10 MB  → Conservative
├─ <50 MB  → Moderate
└─ >50 MB  → Comprehensive

Primary goal?
├─ LLM diff review    → Conservative
├─ Code analysis      → Moderate
└─ Research/forensics → Comprehensive
```

---

## Data Quality & Integrity

### All Three Methods Provide:
- ✅ Complete commit metadata
- ✅ Full diffs for all commits
- ✅ Repository information
- ✅ Structured, parseable data
- ✅ No LLM preprocessing
- ✅ Accurate commit history

### Quality Ratings

| Aspect | Conservative | Moderate | Comprehensive |
|--------|-------------|----------|---------------|
| **Integrity** | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐⭐ |
| **Completeness** | ⭐⭐⭐☆☆ | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐⭐ |
| **Efficiency** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐☆☆ |
| **Usability** | ⭐⭐⭐⭐☆ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐☆ |

---

## Final Recommendation

### For Your Use Case (LLM-based Code Evaluation):

**Primary: Conservative** ⭐⭐⭐
- Smallest size (5.3 MB)
- Lowest token usage (~$3)
- Fastest processing
- Diffs are sufficient for evaluation
- Best cost efficiency

**Alternative: Moderate** ⭐⭐
- If you need file context
- Better architecture understanding
- Still reasonable size (12 MB)
- Good balance (~$9)

**Not Recommended: Comprehensive**
- Too large for LLM processing
- High token costs (~$30)
- Overkill for evaluation
- Better for research

---

## Next Steps

All three extractions are complete and ready:

1. **Conservative**: [data/shuxueshuxue/ink-and-memory-conservative/](data/shuxueshuxue/ink-and-memory-conservative/) (5.3 MB)
2. **Moderate**: [data/shuxueshuxue/ink-and-memory-moderate/](data/shuxueshuxue/ink-and-memory-moderate/) (12 MB)
3. **Comprehensive**: [data/shuxueshuxue/ink-and-memory/](data/shuxueshuxue/ink-and-memory/) (154 MB)

**Total if keeping all three**: 171 MB (still reasonable)

### Documentation:
- [Conservative Summary](shuxueshuxue/ink-and-memory-conservative/EXTRACTION_SUMMARY.md)
- [Moderate Summary](shuxueshuxue/ink-and-memory-moderate/EXTRACTION_SUMMARY.md)
- [Comprehensive Summary](shuxueshuxue/ink-and-memory/EXTRACTION_SUMMARY.md)

---

**Conclusion**: Three extraction methods provide different trade-offs. Conservative is recommended for LLM-based evaluation due to minimal size and cost, while Moderate offers better balance if context is needed, and Comprehensive is ideal for complete research.
