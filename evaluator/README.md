# Engineer Capability Assessment System

A comprehensive evaluation system that analyzes engineer capabilities based on GitHub and Gitee activity. The system uses LLM-powered analysis with a **plugin-based architecture** to evaluate software engineers across multiple dimensions of engineering excellence.

## Overview

The Engineer Capability Assessment System collects data from GitHub/Gitee repositories and commits, then uses AI-powered analysis to evaluate engineering skills across multiple dimensions. It provides:

- **FastAPI Backend** (port 8000) - RESTful API for data extraction and evaluation
- **Next.js Dashboard** (port 3000) - Interactive web UI with charts and PDF export
- **Plugin System** - Extensible evaluation strategies with custom UI components
- **Multi-Alias Support** - Intelligent identity aggregation (~88% token savings)
- **Incremental Sync** - Efficient updates with state tracking
- **Smart Caching** - Three-tier caching (API → Data → Evaluations)

## Quick Start

### From PyPI (Recommended)

```bash
# Install
pip install oscanner-skill-evaluator

# Interactive setup (creates .env.local with LLM API keys)
oscanner init

# Start backend + dashboard together
oscanner dev
# Or backend only: oscanner serve
# Or dashboard only: oscanner dashboard
```

**Dashboard Access:** `http://localhost:3000`
**API Access:** `http://localhost:8000`
**API Docs:** `http://localhost:8000/docs`

### From Source (Development)

```bash
# Install dependencies with uv
uv sync

# Interactive configuration
uv run oscanner init

# Start backend + dashboard together
uv run oscanner dev --reload
# Or start separately:
# Backend: uv run oscanner serve --reload
# Dashboard: uv run oscanner dashboard
```

### oscanner CLI Commands

The `oscanner` CLI provides unified management for the entire system:

```bash
oscanner init           # Interactive setup with API key configuration
oscanner dev            # Start backend + webapp together (development mode)
oscanner serve          # Start FastAPI backend only (port 8000)
oscanner dashboard      # Start Next.js webapp only (port 3000)
oscanner --help         # Show all available commands
```

### Web Dashboard Features

The Next.js dashboard provides three analysis modes:

1. **Single Repository Analysis** (`/`)
   - Enter GitHub/Gitee repository URL
   - Auto-extracts commits if not cached
   - Lists all authors with commit counts
   - Click author to evaluate with default plugin
   - View six-dimensional scores with radar chart
   - Export to PDF with one click

2. **Multi-Repository Analysis** (`/repos`)
   - Compare 2-5 repositories at once
   - Find common contributors across repos
   - Intelligent identity matching (GitHub ID → fuzzy name → exact name)
   - View commit counts per repository
   - Identify cross-project contributors

3. **Contributor Comparison** (from multi-repo page)
   - Compare one contributor across multiple repositories
   - Six-dimensional score comparison
   - Multiple chart types: radar, bar, heatmap, line
   - Identify specialization and context-aware capabilities
   - Export comparison report to PDF

**Settings Page:**
- Configure LLM API key, model, and base URL
- Test LLM connection
- View current configuration (API keys masked)
- Persisted to localStorage + backend

## Key Features

- **Plugin-Based Architecture**: Extensible evaluation strategies with self-contained backend logic and React UI components
- **Six-Dimensional Evaluation Framework**: Comprehensive assessment across AI/ML, architecture, cloud native, collaboration, intelligent development, and leadership
- **Multi-Platform Support**: Works with both GitHub and Gitee repositories (public + enterprise z.gitee.cn)
- **Incremental Sync**: Efficiently fetches only new commits since last sync, tracking sync state (`last_commit_sha`, `last_commit_date`) per repository
- **Multi-Alias Aggregation**: Automatically merges contributor identities (e.g., "CarterWu", "wu-yanbiao") with weighted averaging (~88% token savings)
- **Smart Caching**: Three-tier caching strategy:
  1. API responses (GitHub/Gitee) cached locally
  2. Extracted commit data and diffs
  3. LLM evaluation results per author per plugin
- **LLM-Powered Analysis**: Configurable LLM providers with automatic fallback:
  - OpenRouter (default) with multi-model support
  - OpenAI-compatible APIs (Azure, LocalAI, custom endpoints)
  - Automatic fallback chain (primary → fallback → keyword-based)
- **Dynamic Plugin UI**: React components loaded at runtime from plugin directories
- **Interactive Web Dashboard**: Next.js app with three analysis modes:
  - Single-repo author evaluation
  - Multi-repo common contributor analysis
  - Cross-repo contributor comparison with visualization
- **oscanner CLI**: Unified command-line interface for setup (`init`), development (`dev`), and server management (`serve`, `dashboard`)
- **RESTful API**: 15+ FastAPI endpoints for integration with external systems
- **XDG-Compliant Storage**: Data stored in `~/.local/share/oscanner/` following Linux/Unix standards
- **PDF Export**: One-click export of evaluation reports and comparison charts

## Directory Structure

```
evaluator/
├── __init__.py                          # Package initialization
├── core.py                              # Core evaluation engine (legacy, for compatibility)
├── dimensions.py                        # Six-dimensional evaluation framework (legacy)
├── server.py                            # FastAPI web service (2,457 lines) - Main API engine
├── plugin_registry.py                   # Plugin discovery and loading system
├── sync_manager.py                      # Incremental repository sync management
├── contributtor.py                      # Contributor identity clustering (~88% token savings)
├── paths.py                             # XDG-compliant path management
├── collectors/                          # Data collection modules
│   ├── __init__.py
│   ├── github.py                        # GitHub API collector (public repos)
│   └── gitee.py                         # Gitee API collector (public + enterprise)
├── analyzers/                           # Code analysis modules
│   ├── code_analyzer.py                 # Code quality analyzer
│   ├── commit_analyzer.py               # Commit pattern analyzer
│   └── collaboration_analyzer.py        # Collaboration metrics
├── reporters/                           # Report generation utilities
├── tools/                               # Data extraction tools
│   └── extract_repo_data_moderate.py
└── requirements.txt                     # (legacy) Python dependencies; prefer pyproject.toml + uv

plugins/                                 # Plugin system (extensible evaluators)
├── zgc_simple/                          # Default plugin
│   ├── index.yaml                       # Plugin metadata
│   ├── scan/__init__.py                 # CommitEvaluatorModerate
│   └── view/                            # React UI components
│       ├── single/                      # Single-repo analysis view
│       └── compare/                     # Multi-repo comparison view
└── zgc_ai_native_2026/                  # AI-Native 2026 rubric plugin
    ├── index.yaml
    ├── scan/__init__.py
    └── view/
```

## Six Evaluation Dimensions

### 1. AI Model Full-Stack & Trade-off Capability
Evaluates AI/ML model development, training, optimization, and deployment capabilities.
- ML framework usage (TensorFlow, PyTorch, etc.)
- Model architecture and design
- Training pipelines and optimization
- Model serving and inference optimization
- End-to-end ML pipeline implementation

### 2. AI Native Architecture & Communication Design
Assesses AI-first system design, API design, and microservices architecture.
- AI service API design
- Microservices and distributed systems
- Architecture documentation
- Communication patterns and design
- Integration patterns and scalability

### 3. Cloud Native & Constraint Engineering
Measures containerization, infrastructure as code, and DevOps practices.
- Docker and containerization
- Kubernetes and orchestration
- CI/CD pipelines
- Infrastructure as Code (Terraform, CloudFormation)
- Resource optimization

### 4. Open Source Collaboration & Requirements Translation
Evaluates collaboration quality, communication, and community engagement.
- Contribution frequency and quality
- Code review participation
- Issue management
- Cross-repository collaboration
- Requirements-to-code translation

### 5. Intelligent Development & Human-Machine Collaboration
Assesses automation, tooling, testing, and AI-assisted development.
- Automation scripts and tools
- AI-assisted development practices
- Test automation
- Custom tooling development
- Development efficiency

### 6. Engineering Leadership & System Trade-offs
Measures technical decision-making, mentorship, and architectural leadership.
- Mentorship and code review quality
- Architectural decisions
- Technical decision documentation
- Project ownership
- Team collaboration and leadership

## Installation

### Prerequisites
- Python 3.8+
- pip or [uv](https://github.com/astral-sh/uv) (recommended)

### Recommended Installation

See the [Quick Start](#quick-start) section above for the recommended installation method using `oscanner init`.

### Manual Setup (Alternative)

If you prefer manual configuration:

1. **Install from PyPI:**
```bash
pip install oscanner-skill-evaluator
# Or from source:
# uv sync
```

2. **Create configuration file:**
```bash
# The config file location (choose one):
# - .env.local (current directory)
# - ~/.local/share/oscanner/.env.local (user-wide)
```

3. **Edit configuration with your API keys:**
```env
# LLM Configuration (at least one required)
OPEN_ROUTER_KEY=sk-or-v1-your-key-here
# Or:
# OPENAI_API_KEY=sk-your-openai-key
# Or:
# OSCANNER_LLM_API_KEY=your-custom-api-key

# Optional: Custom LLM configuration
OSCANNER_LLM_MODEL=anthropic/claude-sonnet-4.5
OSCANNER_LLM_BASE_URL=https://openrouter.ai/api/v1
OSCANNER_LLM_FALLBACK_MODELS=z-ai/glm-4.7,meta-llama/llama-3.3-70b-instruct

# GitHub token (optional, for higher API rate limits: 5000/hr vs 60/hr)
GITHUB_TOKEN=ghp_your_github_token

# Gitee tokens (optional, for Gitee repositories)
GITEE_TOKEN=your_gitee_token
GITEE_ENTERPRISE_TOKEN=your_enterprise_token
```

4. **Start the system:**
```bash
oscanner dev  # Backend + Dashboard
# Or separately:
# oscanner serve    # Backend only (port 8000)
# oscanner dashboard  # Dashboard only (port 3000)
```

## Complete Workflow

### System Architecture

The evaluation system follows this intelligent workflow to minimize API calls and maximize caching:

```
┌─────────────────────────────────────────────────────────────────┐
│  User enters GitHub URL (e.g., github.com/owner/repo)          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: GET /api/local/authors/{owner}/{repo}                │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: Check evaluation cache at                             │
│  evaluations/cache/{owner}/{repo}/evaluations.json              │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Cache Hit               Cache Miss
         │                       │
         ▼                       ▼
    Return cached     ┌──────────────────────────┐
    author list       │ Check local data at      │
    instantly ⚡      │ data/{owner}/{repo}/     │
                      └──────────┬───────────────┘
                                 │
                     ┌───────────┴───────────┐
                     │                       │
                Data Exists            Data Missing
                     │                       │
                     │                       ▼
                     │          ┌─────────────────────────────┐
                     │          │ Extract from GitHub using   │
                     │          │ extract_repo_data_moderate  │
                     │          │ (1-2 minutes, once per repo)│
                     │          └──────────┬──────────────────┘
                     │                     │
                     └──────────┬──────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Load all authors from      │
                   │ commit data                │
                   └────────────┬───────────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Auto-evaluate first author │
                   │ with AI (Claude Sonnet 4.5)│
                   └────────────┬───────────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Cache evaluation result    │
                   │ in evaluations.json        │
                   └────────────┬───────────────┘
                                │
                                ▼
                   ┌────────────────────────────┐
                   │ Return all authors list    │
                   └────────────────────────────┘
```

### Evaluation Flow (Per Author)

```
┌─────────────────────────────────────────────────────────────────┐
│  User clicks on author                                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: POST /api/evaluate/{owner}/{repo}/{author}           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: Check if author exists in evaluation cache            │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Cache Hit               Cache Miss
         │                       │
         ▼                       ▼
    Return cached     ┌──────────────────────────┐
    evaluation        │ Load commits from local  │
    instantly ⚡      │ data (up to 30 commits)  │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Create evaluator with    │
                      │ repository context       │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Evaluate author with AI  │
                      │ - Analyze commit diffs   │
                      │ - Read relevant files    │
                      │ - Score 6 dimensions     │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Cache evaluation result  │
                      └──────────┬───────────────┘
                                 │
                                 ▼
                      ┌──────────────────────────┐
                      │ Return evaluation        │
                      └──────────────────────────┘
```

### Chunking and Linear Evaluation

The system uses a **chunking and linear evaluation algorithm** to handle large commit histories while staying within LLM context limits. This approach prioritizes accuracy and correlation over raw speed.

#### Algorithm Overview

When evaluating an author with many commits (e.g., 50-100+), the system:

1. **Divides commits into N chunks** based on LLM's maximum context window
2. **Evaluates chunks sequentially** (one after another, not in parallel)
3. **Accumulates insights** from previous chunks to inform subsequent evaluations
4. **Produces coherent, contextualized results** across the entire commit history

#### Why Linear Instead of Parallel?

**Linear Evaluation (Current Approach):**
- ✅ Better accuracy - LLM sees progression of work over time
- ✅ Stronger correlation - Later chunks informed by earlier insights
- ✅ Contextual understanding - Growth patterns and skill development visible
- ✅ Coherent narrative - Single evaluation story across all commits
- ❌ Slower - Must wait for each chunk to complete

**Parallel Evaluation (Alternative):**
- ✅ Faster - All chunks evaluated simultaneously
- ❌ Worse accuracy - Missing temporal context
- ❌ Weaker correlation - Chunks evaluated in isolation
- ❌ Fragmented insights - Harder to synthesize overall assessment

#### Chunking Strategy

```python
# Pseudocode for chunking algorithm
def chunk_commits(commits, max_tokens_per_chunk):
    """
    Divide commits into chunks that fit within LLM context limits.

    Args:
        commits: List of commit objects (newest first)
        max_tokens_per_chunk: Maximum tokens per chunk (e.g., 190,000)

    Returns:
        List of commit chunks, ordered chronologically
    """
    chunks = []
    current_chunk = []
    current_tokens = 0

    # Process commits in reverse chronological order
    for commit in commits:
        commit_tokens = estimate_tokens(commit)

        if current_tokens + commit_tokens > max_tokens_per_chunk:
            # Start new chunk
            chunks.append(current_chunk)
            current_chunk = [commit]
            current_tokens = commit_tokens
        else:
            current_chunk.append(commit)
            current_tokens += commit_tokens

    # Add final chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks
```

#### Linear Evaluation Process

```
┌─────────────────────────────────────────────────────────────────┐
│  Load author's commits (e.g., 100 commits)                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Divide into N chunks based on token limits                     │
│  Example: 100 commits → 4 chunks of 25 commits each             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │  Chunk 1 (oldest 25)  │
         │  Evaluate with LLM    │
         │  Get initial scores   │
         └───────────┬───────────┘
                     │
                     ▼
         ┌───────────────────────────────────┐
         │  Chunk 2 (next 25)                │
         │  Evaluate with context from Ch1   │
         │  Update accumulated scores        │
         └───────────┬───────────────────────┘
                     │
                     ▼
         ┌───────────────────────────────────┐
         │  Chunk 3 (next 25)                │
         │  Evaluate with context from Ch1-2 │
         │  Refine scores based on patterns  │
         └───────────┬───────────────────────┘
                     │
                     ▼
         ┌───────────────────────────────────┐
         │  Chunk 4 (newest 25)              │
         │  Final evaluation with full       │
         │  historical context               │
         └───────────┬───────────────────────┘
                     │
                     ▼
         ┌───────────────────────────────────┐
         │  Synthesize final evaluation      │
         │  - Overall scores (6 dimensions)  │
         │  - Growth trajectory              │
         │  - Key strengths/weaknesses       │
         │  - Contextual insights            │
         └───────────────────────────────────┘
```

#### Integration with Incremental Sync

The chunking algorithm seamlessly integrates with incremental sync:

```
Initial Evaluation (100 commits):
  Chunk 1 (commits 1-25)   → Evaluate → Cache result
  Chunk 2 (commits 26-50)  → Evaluate → Cache result
  Chunk 3 (commits 51-75)  → Evaluate → Cache result
  Chunk 4 (commits 76-100) → Evaluate → Cache result
  → Final evaluation cached

After 2 weeks (20 new commits):
  Chunks 1-4 (cached, reused)
  Chunk 5 (commits 101-120) → Evaluate with Ch1-4 context
  → Updated final evaluation cached
```

**Key Benefits:**
- **Incremental cost**: Only evaluate new chunk, reuse previous chunks
- **Token efficiency**: Previous chunks' results summarized, not re-evaluated
- **Consistent baseline**: Historical evaluation preserved
- **Growth tracking**: Clear comparison between old and new contributions

#### Implementation Example

```python
class ChunkedLinearEvaluator:
    def evaluate_with_chunking(self, author: str, commits: list):
        # 1. Load cached chunk evaluations if available
        cached_chunks = self.load_cached_chunks(author)

        # 2. Determine which commits are new (incremental sync)
        if cached_chunks:
            last_evaluated_sha = cached_chunks[-1]['last_commit_sha']
            new_commits = [c for c in commits if is_after(c, last_evaluated_sha)]
            all_chunk_results = cached_chunks
        else:
            new_commits = commits
            all_chunk_results = []

        # 3. Chunk new commits
        new_chunks = self.chunk_commits(new_commits, max_tokens=190000)

        # 4. Evaluate each new chunk linearly
        accumulated_context = self.summarize_chunks(all_chunk_results)

        for chunk_idx, chunk in enumerate(new_chunks):
            chunk_evaluation = self.evaluate_chunk(
                chunk=chunk,
                previous_context=accumulated_context,
                chunk_number=len(all_chunk_results) + chunk_idx + 1
            )

            # Cache chunk result
            all_chunk_results.append(chunk_evaluation)
            self.cache_chunk(author, chunk_evaluation)

            # Update accumulated context for next chunk
            accumulated_context = self.update_context(
                accumulated_context,
                chunk_evaluation
            )

        # 5. Synthesize final evaluation from all chunks
        final_evaluation = self.synthesize_final(all_chunk_results)

        return final_evaluation

    def evaluate_chunk(self, chunk, previous_context, chunk_number):
        """
        Evaluate a single chunk with context from previous chunks.

        LLM prompt includes:
        - Commits in this chunk (full diffs)
        - Summary of previous chunks' findings
        - Running scores from previous chunks
        - Patterns observed so far
        """
        prompt = f"""
        You are evaluating chunk {chunk_number} of an engineer's work.

        Previous context:
        {previous_context}

        Current chunk commits:
        {format_commits(chunk)}

        Evaluate this chunk considering:
        1. How it builds on previous work
        2. Skill progression or regression
        3. New capabilities demonstrated
        4. Consistency with earlier patterns

        Provide scores for each dimension.
        """

        response = self.llm_client.chat_completion(prompt)
        return parse_chunk_evaluation(response)
```

#### Performance Characteristics

**Token Usage:**
- First-time evaluation (100 commits, 4 chunks):
  - Chunk 1: ~50k tokens (no context)
  - Chunk 2: ~55k tokens (Ch1 summary)
  - Chunk 3: ~60k tokens (Ch1-2 summary)
  - Chunk 4: ~65k tokens (Ch1-3 summary)
  - **Total: ~230k tokens**

- Incremental evaluation (+20 commits, 1 new chunk):
  - Chunk 5: ~70k tokens (Ch1-4 summary reused)
  - **Total: ~70k tokens** (70% savings)

**Time Comparison:**
- Linear evaluation: ~2-3 minutes (sequential API calls)
- Parallel evaluation: ~30-45 seconds (simultaneous calls)
- **Trade-off**: 4x slower but significantly more accurate

#### When Chunking is Applied

Chunking activates automatically when:
- Author has > 30 commits (configurable threshold)
- Estimated total tokens exceed `max_input_tokens` (default: 190,000)
- Incremental sync brings new commits that create a new chunk

For small commit counts (< 30), the system evaluates all commits in a single LLM call.

### Batch Repository Comparison (/repos Page)

The system supports comparing multiple repositories to find common contributors, useful for:
- Identifying developers with experience across multiple projects
- Finding potential collaborators
- Analyzing cross-project contributions
- Team composition analysis

#### Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  User enters 2-5 GitHub repository URLs                         │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: POST /api/batch/extract                              │
│  Extracts data for all repositories                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         │                       │
    Data Exists             Data Missing
         │                       │
         ▼                       ▼
    Skip extraction    ┌──────────────────────────┐
                       │ Extract from GitHub      │
                       │ (1-2 min per repo)       │
                       └──────────┬───────────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend: POST /api/batch/common-contributors                  │
│  Analyzes all repositories for common contributors              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: Intelligent Contributor Matching (3-pass algorithm)   │
│                                                                  │
│  Pass 1: Group by GitHub ID/login (strong identity signals)     │
│  Pass 2: Fuzzy name matching for orphaned authors               │
│  Pass 3: Exact name matching for remaining authors              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Return common contributors with:                               │
│  - Author name (most complete version)                          │
│  - GitHub login                                                 │
│  - Email address                                                │
│  - Commit counts per repository                                 │
│  - Total commits across all repos                               │
│  - Matching method used (github_id, github_login, or name)      │
└─────────────────────────────────────────────────────────────────┘
```

#### Intelligent Contributor Matching

The system uses a sophisticated three-pass matching algorithm to identify the same person across repositories, even when they use different names or email addresses:

**Pass 1: GitHub ID/Login Matching**
- Groups contributors by GitHub user ID (strongest signal)
- Falls back to GitHub login if ID unavailable
- Creates identity anchors for fuzzy matching

**Pass 2: Fuzzy Name Matching**
- Matches orphaned authors (no GitHub ID) to existing groups
- Compares first names: "Sebastian" matches "Sebastian Markbage"
- Handles common name variations and shortened names
- Useful for old SVN-converted repositories

**Pass 3: Exact Name Matching**
- Groups remaining unmatched authors by exact normalized name
- Fallback for completely unique contributors

**Example Matching Cases:**
```json
{
  "matched_by": "github_id",
  "author": "Sebastian Markbage",
  "github_login": "sebmarkbage",
  "repos": [
    {
      "repo": "animation-timelines",
      "commits": 15,
      "email": "sebastian@calyptus.eu"
    },
    {
      "repo": "calyptus.mvc",
      "commits": 68,
      "email": "Sebastian@8f9bea60-9d31-4c44-a11a-6657d2e7921d"
    }
  ]
}
```

In this example, even though the emails are different and one repo has "Sebastian" while the other has "Sebastian Markbage", the system correctly identifies them as the same person through GitHub ID matching and fuzzy name matching.

### Directory Structure After Processing

Data is stored in XDG-compliant paths: `~/.local/share/oscanner/`

```
~/.local/share/oscanner/
├── data/                                    # Repository data (extracted once)
│   └── {platform}/                          # github or gitee
│       └── {owner}/
│           └── {repo}/
│               ├── repo_info.json           # Repository metadata
│               ├── repo_tree.json           # File tree structure
│               ├── commits_index.json       # Index of all commits
│               ├── commits_list.json        # Raw API commit list
│               ├── sync_state.json          # Incremental sync state
│               │                            # {
│               │                            #   "last_commit_sha": "abc123...",
│               │                            #   "last_commit_date": "2026-01-20T...",
│               │                            #   "last_synced_at": "2026-01-22T..."
│               │                            # }
│               ├── commits/
│               │   ├── {sha}.json           # Commit metadata + diff
│               │   └── {sha}.diff           # Commit diff (separate)
│               └── files/
│                   └── {filepath}           # Current file contents
│
└── evaluations/                             # Cached evaluations
    └── {platform}/
        └── {owner}/
            └── {repo}/
                ├── {author}.json            # Author evaluation (default plugin)
                └── {author}__{plugin_id}.json  # Plugin-specific evaluation
                                            # {
                                            #   "evaluation": {...},
                                            #   "timestamp": "...",
                                            #   "cached": true,
                                            #   "plugin_id": "zgc_simple"
                                            # }
```

### Performance Benefits

**First Repository Access (New):**
- 1-2 minutes to extract data from GitHub
- AI evaluation for first author (~10-20 seconds)
- Total: ~2 minutes

**Second+ Repository Access (Cached):**
- Authors list: **Instant** (from cache)
- First author evaluation: **Instant** (from cache)
- Other authors: First click ~10-20 seconds, then instant
- Total: **< 1 second**

**Batch Repository Comparison (2-5 repos):**
- First extraction: 1-2 minutes per repo (parallel processing)
- Already extracted: **Instant** skip
- Common contributors analysis: **< 2 seconds** (pure computation)
- Total first-time: ~2-5 minutes for all repos
- Total cached: **< 2 seconds**

**Token Usage:**
- Without caching: ~50-100k tokens per evaluation × N authors = expensive
- With caching: ~50-100k tokens × N unique evaluations = efficient
- Cache hit rate: Typically 80-90% after initial use
- Batch comparison: **0 tokens** (no LLM calls, pure data analysis)

## Usage

### 1. Programmatic Usage

```python
from evaluator import EngineerEvaluator

# Initialize evaluator
config = {
    "github_token": "your_github_token",
    "gitee_token": "your_gitee_token"
}
evaluator = EngineerEvaluator(config)

# Evaluate a GitHub user
result = evaluator.evaluate(
    github_username="octocat",
    repos=["https://github.com/octocat/Hello-World"]
)

# Print text report
print(result.get_report(format="text"))

# Get JSON output
print(result.get_report(format="json"))

# Access specific information
print(f"Overall Score: {result.overall_score}")
print(f"Top Strengths: {result.get_top_dimensions(3)}")
print(f"Areas to Develop: {result.get_bottom_dimensions(3)}")
```

### 2. FastAPI Web Service

Start the server:

```bash
python server.py
# or
./start_server.sh
```

The server will start on `http://localhost:8000` with the following endpoints:

#### API Endpoints

**Infrastructure:**
```
GET /health                              # Health check
GET /                                    # Root redirect to dashboard
GET /favicon.ico                         # Favicon (no-op)
```

**Plugin & Configuration Management:**
```
GET /api/plugins                         # List available evaluation plugins
GET /api/plugins/default                 # Get default plugin ID
GET /api/config/llm                      # Read LLM configuration (API keys masked)
POST /api/config/llm                     # Configure LLM settings (API key, model, base URL)
GET /api/llm/status                      # Check LLM configuration status
```

**Data & Author Management:**
```
GET /api/authors/{owner}/{repo}          # List commit authors (auto-extracts if needed)
```
Returns all authors with intelligent caching:
- Checks evaluation cache first
- If missing, checks local data
- If missing, extracts from GitHub/Gitee automatically
- Auto-evaluates first author with default plugin

```
GET /api/gitee/commits/{owner}/{repo}?limit=100&is_enterprise=false
```
Fetch Gitee commits directly from API.

**Evaluation Endpoints:**
```
POST /api/evaluate/{owner}/{repo}/{author}?limit=30&plugin_id=zgc_simple
```
**Primary evaluation endpoint** with advanced features:
- Supports **author aliases**: Pass `{"aliases": ["name1", "name2"]}` in request body
- Evaluates each alias separately (cached results reused)
- Weighted merge based on commit count (~88% token savings)
- LLM-synthesized unified analysis across identities
- Auto-syncs repository with incremental fetch (only new commits)
- Returns cached result if available
- Plugin-specific evaluation (`plugin_id` parameter)

```
POST /api/merge-evaluations
```
Merge multiple author evaluations with weighted averaging:
```json
{
  "evaluations": [
    {"author": "name1", "evaluation": {...}, "commit_count": 50},
    {"author": "name2", "evaluation": {...}, "commit_count": 30}
  ]
}
```

```
POST /api/gitee/evaluate/{owner}/{repo}/{contributor}?limit=30
```
Gitee-specific evaluation endpoint (legacy compatibility).

**Batch Operations:**
```
POST /api/batch/extract
```
Extract data from multiple GitHub repositories (2-5 repos):
```json
{
  "urls": [
    "https://github.com/owner1/repo1",
    "https://github.com/owner2/repo2"
  ]
}
```

```
POST /api/batch/common-contributors
```
Find developers who contributed to multiple repositories:
```json
{
  "repos": [
    {"owner": "owner1", "repo": "repo1"},
    {"owner": "owner2", "repo": "repo2"}
  ]
}
```
Uses **three-pass matching algorithm**:
1. GitHub ID/login matching (strongest signal)
2. Fuzzy name matching for orphaned authors
3. Exact name matching for unique contributors

```
POST /api/batch/compare-contributor
```
Compare a contributor's capability scores across multiple repositories:
```json
{
  "contributor": "John Doe",
  "repos": [
    {"owner": "facebook", "repo": "react"},
    {"owner": "vercel", "repo": "next.js"}
  ],
  "plugin_id": "zgc_simple"
}
```
Returns evaluation data for visualization (radar, bar, heatmap, line charts).

#### Example API Calls

```bash
# Health check
curl "http://localhost:8000/health"

# List available plugins
curl "http://localhost:8000/api/plugins"

# Get default plugin
curl "http://localhost:8000/api/plugins/default"

# Check LLM configuration status
curl "http://localhost:8000/api/llm/status"

# Configure LLM (will be saved to .env.local)
curl -X POST "http://localhost:8000/api/config/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "sk-or-v1-your-key",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "anthropic/claude-sonnet-4.5"
  }'

# Get authors list (auto-fetches and caches if needed)
curl "http://localhost:8000/api/authors/anthropics/anthropic-sdk-python"

# Evaluate a specific author with default plugin
curl -X POST "http://localhost:8000/api/evaluate/anthropics/anthropic-sdk-python/octocat?limit=30"

# Evaluate with specific plugin
curl -X POST "http://localhost:8000/api/evaluate/anthropics/anthropic-sdk-python/octocat?plugin_id=zgc_ai_native_2026"

# Evaluate author with aliases (multi-identity aggregation)
curl -X POST "http://localhost:8000/api/evaluate/facebook/react/Dan%20Abramov?limit=30" \
  -H "Content-Type: application/json" \
  -d '{
    "aliases": ["Dan Abramov", "dan_abramov", "gaearon"]
  }'

# Merge multiple evaluations with weighted averaging
curl -X POST "http://localhost:8000/api/merge-evaluations" \
  -H "Content-Type: application/json" \
  -d '{
    "evaluations": [
      {
        "author": "Dan Abramov",
        "evaluation": {...},
        "commit_count": 150
      },
      {
        "author": "gaearon",
        "evaluation": {...},
        "commit_count": 80
      }
    ]
  }'

# Batch extract multiple repositories
curl -X POST "http://localhost:8000/api/batch/extract" \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://github.com/facebook/react", "https://github.com/vercel/next.js"]}'

# Find common contributors across repositories
curl -X POST "http://localhost:8000/api/batch/common-contributors" \
  -H "Content-Type: application/json" \
  -d '{"repos": [{"owner": "facebook", "repo": "react"}, {"owner": "vercel", "repo": "next.js"}]}'

# Compare contributor across multiple repositories
curl -X POST "http://localhost:8000/api/batch/compare-contributor" \
  -H "Content-Type: application/json" \
  -d '{"contributor": "Sebastian Markbage", "repos": [{"owner": "facebook", "repo": "react"}, {"owner": "vercel", "repo": "next.js"}], "plugin_id": "zgc_simple"}'

# Gitee-specific: Get commits
curl "http://localhost:8000/api/gitee/commits/owner/repo?limit=100&is_enterprise=false"

# Gitee-specific: Evaluate contributor
curl -X POST "http://localhost:8000/api/gitee/evaluate/owner/repo/contributor?limit=30"
```

### 3. LLM-Based Commit Evaluation

```python
from evaluator.commit_evaluator import CommitEvaluator
from evaluator.collectors.github import GitHubCollector

# Initialize
collector = GitHubCollector(token="your_github_token")
evaluator = CommitEvaluator(api_key="your_openrouter_key")

# Fetch commits
commits = collector.fetch_commits_list("owner", "repo", limit=100)

# Filter commits by author
author_commits = [
    c for c in commits
    if c.get("commit", {}).get("author", {}).get("name") == "Author Name"
]

# Evaluate engineer
result = evaluator.evaluate_engineer(
    commits=author_commits,
    username="Author Name",
    max_commits=20
)

print(f"Scores: {result['scores']}")
print(f"Summary: {result['commits_summary']}")
```

## Caching Strategy

The system implements intelligent caching to optimize performance and reduce costs:

### 1. API Response Caching
- GitHub/Gitee API responses are cached locally in `data/` directory
- Commits are cached per repository
- Cache is automatically checked before making API calls

### 2. Evaluation Result Caching
- LLM evaluation results are cached to avoid redundant API calls
- Cache is stored in `evaluations/` subdirectories

### 3. Repository Context Caching
- Full repository context is cached in-memory during server runtime
- Evaluating multiple contributors from the same repo reuses cached context
- Significantly reduces token usage and response time

## Data Storage

### XDG-Compliant Local Storage

All data is stored locally following XDG Base Directory specification:

**Base Directory:** `~/.local/share/oscanner/` (or `$OSCANNER_HOME` if set)

### Data Structure

```
~/.local/share/oscanner/
├── data/                                    # Extracted repository data
│   ├── github/                              # GitHub repositories
│   │   └── {owner}/
│   │       └── {repo}/
│   │           ├── repo_info.json           # Repository metadata
│   │           ├── commits_index.json       # Index of all commit SHAs
│   │           ├── sync_state.json          # Incremental sync tracking
│   │           ├── commits/
│   │           │   ├── {sha}.json           # Commit metadata + diff
│   │           │   └── {sha}.diff           # Commit diff (separate file)
│   │           └── files/
│   │               └── {filepath}           # File contents at HEAD
│   └── gitee/                               # Gitee repositories (same structure)
│
├── evaluations/                             # Cached evaluation results
│   ├── github/
│   │   └── {owner}/
│   │       └── {repo}/
│   │           ├── {author}.json            # Default plugin evaluation
│   │           └── {author}__zgc_ai_native_2026.json  # Plugin-specific
│   └── gitee/
│
└── .env.local                               # User-specific configuration
```

### Sync State Tracking

Each repository maintains incremental sync state in `sync_state.json`:

```json
{
  "last_commit_sha": "abc123def456...",
  "last_commit_date": "2026-01-20T10:30:45Z",
  "last_synced_at": "2026-01-22T15:20:10Z"
}
```

This enables **incremental data fetching**:
- Only fetch commits newer than `last_commit_date`
- Dramatically reduces API calls and processing time
- Atomic writes prevent data corruption

### Evaluation Cache Format

Evaluation results are cached per author per plugin:

```json
{
  "evaluation": {
    "overall_score": 85,
    "dimension_scores": {
      "ai_model_fullstack": 90,
      "ai_native_architecture": 85,
      "cloud_native": 80,
      "collaboration": 88,
      "intelligent_development": 82,
      "leadership": 85
    },
    "strengths": ["..."],
    "weaknesses": ["..."],
    "summary": "...",
    "commit_count": 45
  },
  "timestamp": "2026-01-22T15:20:10Z",
  "cached": true,
  "plugin_id": "zgc_simple",
  "model_used": "anthropic/claude-sonnet-4.5"
}
```

### Cache Invalidation

Caches are automatically invalidated when:
- New commits are fetched (sync_state changes)
- Plugin is updated (different plugin_id)
- Manual cache clear requested

### Storage Management

**Typical Storage Usage:**
- Small repo (100 commits): ~10-50 MB
- Medium repo (1000 commits): ~100-500 MB
- Large repo (10000 commits): ~1-5 GB

**Manual Cleanup:**
```bash
# Clear all data
rm -rf ~/.local/share/oscanner/data

# Clear evaluations only (keep extracted data)
rm -rf ~/.local/share/oscanner/evaluations

# Clear specific repository
rm -rf ~/.local/share/oscanner/data/github/owner/repo
rm -rf ~/.local/share/oscanner/evaluations/github/owner/repo
```

## Configuration

### Environment Variables

The system uses a **priority-based configuration system** with multiple sources:

**Configuration File Priority:**
1. `.env.local` (project-local, in current working directory)
2. `~/.local/share/oscanner/.env.local` (user dotfile)
3. `.env` (default template)
4. Process environment variables

**Core Variables:**

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| **LLM Configuration** |
| `OSCANNER_LLM_API_KEY` | Primary LLM API key | Yes* | - |
| `OPENAI_API_KEY` | Secondary LLM API key | Yes* | - |
| `OPEN_ROUTER_KEY` | Fallback LLM API key (OpenRouter) | Yes* | - |
| `OSCANNER_LLM_MODEL` | Default LLM model name | No | `Pro/zai-org/GLM-4.7` |
| `OSCANNER_LLM_BASE_URL` | Custom LLM endpoint base URL | No | `https://openrouter.ai/api/v1` |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL | No | - |
| `OSCANNER_LLM_CHAT_COMPLETIONS_URL` | Full chat completions endpoint URL | No | `{base_url}/chat/completions` |
| `OSCANNER_LLM_FALLBACK_MODELS` | Comma-separated fallback model list | No | - |
| **Platform API Tokens** |
| `GITHUB_TOKEN` | GitHub personal access token | No | - |
| `GITEE_TOKEN` | Gitee public API token | No | - |
| `GITEE_ENTERPRISE_TOKEN` | Gitee enterprise (z.gitee.cn) token | No | - |
| **Path Configuration** |
| `OSCANNER_HOME` | Base directory for all data | No | See below |
| `XDG_DATA_HOME` | XDG base directory | No | `~/.local/share` |
| `OSCANNER_DATA_DIR` | Override data directory | No | `{OSCANNER_HOME}/data` |
| `OSCANNER_PLUGINS_DIR` | Override plugins directory | No | `<repo>/plugins` |
| **Server Configuration** |
| `PORT` | Server port | No | `8000` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING) | No | `INFO` |

\* At least one LLM API key is required (checked in priority order)

**Path Resolution:**

Base directory (`OSCANNER_HOME`):
1. `$OSCANNER_HOME` (if set)
2. `$XDG_DATA_HOME/oscanner` (if XDG_DATA_HOME set)
3. `~/.local/share/oscanner` (default)

Data directory:
1. `$OSCANNER_DATA_DIR` (if set)
2. `{OSCANNER_HOME}/data` (default)

Evaluations directory:
1. `{OSCANNER_HOME}/evaluations` (fixed)

**Example Configuration:**

```env
# .env.local

# LLM Configuration (OpenRouter)
OPEN_ROUTER_KEY=sk-or-v1-your-key-here
OSCANNER_LLM_MODEL=anthropic/claude-sonnet-4.5
OSCANNER_LLM_FALLBACK_MODELS=z-ai/glm-4.7,meta-llama/llama-3.3-70b-instruct

# GitHub API (optional, for higher rate limits)
GITHUB_TOKEN=ghp_your_token_here

# Gitee API (optional)
GITEE_TOKEN=your_gitee_token
GITEE_ENTERPRISE_TOKEN=your_enterprise_token

# Path overrides (optional)
OSCANNER_HOME=/custom/path/oscanner
OSCANNER_PLUGINS_DIR=/custom/plugins

# Server configuration
PORT=8080
LOG_LEVEL=DEBUG
```

### Evaluation Parameters

- `max_commits`: Maximum commits to analyze (default varies by evaluator)
- `max_input_tokens`: Maximum tokens for LLM input (default: 190,000)

### LLM Model Configuration

The system provides flexible LLM configuration with multiple providers and fallback options.

**Configuration Priority:**

1. **API Keys** (checked in order):
   - `OSCANNER_LLM_API_KEY` (primary)
   - `OPENAI_API_KEY` (secondary)
   - `OPEN_ROUTER_KEY` (fallback)

2. **Base URL** (checked in order):
   - `OSCANNER_LLM_BASE_URL` (custom endpoint)
   - `OPENAI_BASE_URL` (OpenAI-compatible)
   - `https://openrouter.ai/api/v1` (default)

3. **Chat Completions Endpoint**:
   - `OSCANNER_LLM_CHAT_COMPLETIONS_URL` (full custom URL)
   - Or `{base_url}/chat/completions` (constructed)

4. **Model Selection**:
   - `OSCANNER_LLM_MODEL` (default: `Pro/zai-org/GLM-4.7`)
   - Model names are provider-specific

5. **Fallback Models**:
   - `OSCANNER_LLM_FALLBACK_MODELS` (comma-separated list)
   - Example: `anthropic/claude-sonnet-4.5,z-ai/glm-4.7`

**Supported Providers:**
- OpenRouter (default) - Multi-model gateway
- OpenAI-compatible APIs (Azure, LocalAI, etc.)
- Custom endpoints via environment variables

**How Fallback Works:**
1. System tries primary model first
2. If API error/timeout/rate limit → tries first fallback model
3. If all LLMs fail → uses keyword-based heuristic evaluation
4. All transitions are logged with model used and token usage

**Example Configuration:**

```env
# OpenRouter (default)
OPEN_ROUTER_KEY=sk-or-v1-your-key-here
OSCANNER_LLM_MODEL=anthropic/claude-sonnet-4.5
OSCANNER_LLM_FALLBACK_MODELS=z-ai/glm-4.7,meta-llama/llama-3.3-70b-instruct

# OpenAI
OPENAI_API_KEY=sk-your-key
OSCANNER_LLM_MODEL=gpt-4-turbo

# Custom endpoint (e.g., LocalAI)
OSCANNER_LLM_API_KEY=your-key
OSCANNER_LLM_BASE_URL=http://localhost:8080/v1
OSCANNER_LLM_MODEL=mistral-7b-instruct
```

**Runtime Configuration:**
You can also configure LLM settings via the web UI Settings page or API:

```bash
# Update LLM configuration via API
curl -X POST "http://localhost:8000/api/config/llm" \
  -H "Content-Type: application/json" \
  -d '{
    "api_key": "sk-or-v1-your-key",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "anthropic/claude-sonnet-4.5"
  }'

# Check LLM status
curl "http://localhost:8000/api/llm/status"
```

**Token Usage:**
- Max input tokens: 190,000 (configurable per evaluator)
- The system automatically truncates context to fit token limits
- Caching reduces redundant LLM calls by ~80-90%

## Advanced Features

### Plugin Architecture

The system uses a **plugin-based architecture** for extensible evaluation strategies. Plugins are self-contained modules that provide:
- **Evaluation logic** (`scan/__init__.py`) - Backend evaluator
- **UI components** (`view/`) - React components for visualization

**Plugin Discovery:**
- Plugins directory: `<repo_root>/plugins/` or `$OSCANNER_PLUGINS_DIR`
- Each plugin has an `index.yaml` metadata file

**Plugin Metadata (index.yaml):**
```yaml
id: zgc_simple
name: "Simple Commit Evaluator"
description: "Moderate-complexity evaluation using CommitEvaluatorModerate"
version: "1.0.0"
scan_entry: "scan/__init__.py"          # Backend evaluator module
view_single_entry: "view/single"        # Single-repo React component
view_compare_entry: "view/compare"      # Multi-repo comparison component
default: true                           # Mark as default plugin
```

**Available Plugins:**
1. **zgc_simple** (default)
   - Uses `CommitEvaluatorModerate` class
   - Analyzes commit diffs + local file contents
   - Max input tokens: 190,000
   - Six-dimensional evaluation framework

2. **zgc_ai_native_2026**
   - Rubric-guided evaluation
   - 2026 AI-Native engineering standard
   - Specialized for AI-first architectures

**Plugin Contract:**

Backend evaluator (`scan/__init__.py`) must export:
```python
def create_commit_evaluator(
    api_key: str,
    model: str,
    base_url: str,
    **kwargs
) -> CommitEvaluator:
    """Factory function to create evaluator instance."""
    return MyEvaluator(api_key, model, base_url)
```

Frontend components (`view/`) must export:
```typescript
// view/single/index.tsx
export default function SingleRepoView({ data, config }) {
  // Render single-repo analysis
}

// view/compare/index.tsx
export default function CompareView({ data, config }) {
  // Render multi-repo comparison
}
```

**Using Plugins:**

```bash
# List available plugins
curl "http://localhost:8000/api/plugins"

# Get default plugin
curl "http://localhost:8000/api/plugins/default"

# Evaluate with specific plugin
curl -X POST "http://localhost:8000/api/evaluate/owner/repo/author?plugin_id=zgc_ai_native_2026"
```

**Creating Custom Plugins:**

1. Create plugin directory: `plugins/my_plugin/`
2. Add `index.yaml` with metadata
3. Implement `scan/__init__.py` with evaluator logic
4. Add React components in `view/single/` and `view/compare/`
5. Plugin is auto-discovered on server restart

**Plugin Isolation:**
- Plugins are **self-contained** - must not import from main `evaluator/` package
- Evaluations are cached per plugin: `{author}__{plugin_id}.json`
- UI components loaded dynamically at runtime

### Full Context Evaluation

The `FullContextCachedEvaluator` provides the most comprehensive evaluation:

```python
from evaluator.full_context_cached_evaluator import FullContextCachedEvaluator

evaluator = FullContextCachedEvaluator(
    data_dir="data/owner/repo",
    api_key="your_openrouter_key"
)

result = evaluator.evaluate_contributor(
    contributor_name="Author Name"
)
```

### Repository-Wide Evaluation

```python
from evaluator.full_repo_evaluator import FullRepoEvaluator

evaluator = FullRepoEvaluator(api_key="your_openrouter_key")
result = evaluator.evaluate_repository("owner/repo")
```

## Development

### Running Tests

```bash
# Example evaluation with local data
python example_moderate_evaluation.py
```

### Starting Development Server

```bash
# With auto-reload
uvicorn server:app --reload --port 8000

# Or use the startup script
./start_server.sh
```

## API Documentation

When the server is running, access interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Performance Considerations

### Token Usage Optimization

1. **Commit Sampling**: Analyzes top N commits (default 20-30) instead of all commits
2. **Context Truncation**: Automatically truncates context to fit token limits
3. **Smart Caching**: Caches both API responses and LLM evaluations
4. **Repository Context Reuse**: Shares repository context across multiple contributor evaluations

### Rate Limiting

- GitHub API: 5,000 requests/hour (authenticated), 60/hour (unauthenticated)
- Gitee API: Varies by plan
- OpenRouter: Depends on your plan and selected model

Use tokens and caching to stay within rate limits.

## Troubleshooting

### Common Issues

**Issue: "No API key configured"**
- Solution: Set `OPEN_ROUTER_KEY` in `.env.local`

**Issue: "Failed to fetch GitHub commits"**
- Solution: Check your `GITHUB_TOKEN` and repository access permissions

**Issue: "Context truncated to fit token limit"**
- Solution: This is normal behavior. Adjust `max_input_tokens` if needed

**Issue: "No local data found"**
- Solution: First fetch data using API endpoints or manually populate `data/` directory

**Issue: "No Common Contributors Found" despite same author**
- Cause: Different author names across repositories (e.g., "John" vs "John Doe")
- Solution: The system automatically handles this with fuzzy matching
- Check the `matched_by` field in the response to see how matching was performed
- If still not matching, the names may be too different (e.g., completely different names)

**Issue: Batch extraction fails for some repositories**
- Solution: Check repository access permissions and GitHub token
- Private repositories require a token with appropriate permissions
- Some repositories may have unusual structures or no commit history

**Issue: Common contributors showing duplicate entries**
- Cause: Edge case in fuzzy matching algorithm
- Solution: Check if authors have significantly different emails or no GitHub ID
- The system prioritizes GitHub ID > Login > Name for matching

### Debug Mode

Enable verbose logging:

```bash
export LOG_LEVEL=DEBUG
python server.py
```

## Use Cases

### 1. Identifying Cross-Project Contributors
Find developers who contributed to multiple related projects:
```bash
# Example: Find contributors across React ecosystem projects
curl -X POST "http://localhost:8000/api/batch/common-contributors" \
  -H "Content-Type: application/json" \
  -d '{
    "repos": [
      {"owner": "facebook", "repo": "react"},
      {"owner": "vercel", "repo": "next.js"},
      {"owner": "remix-run", "repo": "remix"}
    ]
  }'
```

### 2. Hiring and Recruitment
Identify candidates with diverse experience:
- Look for contributors across your tech stack
- Find developers familiar with similar domains
- Assess breadth of open source contributions

### 3. Team Composition Analysis
Understand contributor overlap in your organization:
- Find developers working across multiple internal projects
- Identify potential knowledge silos
- Plan cross-team collaboration

### 4. Open Source Community Analysis
Study contribution patterns:
- Track contributor mobility across projects
- Identify core community members
- Understand ecosystem dynamics

### Best Practices

**Repository Selection:**
- Choose 2-5 repositories for optimal performance
- Select related projects for meaningful results
- Mix of sizes (small + large) works well

**Matching Confidence:**
- `matched_by: "github_id"` - Highest confidence (same GitHub account)
- `matched_by: "github_login"` - High confidence (same username)
- `matched_by: "name"` - Medium confidence (fuzzy name match)

**Handling Old Repositories:**
- SVN-converted repos may lack GitHub IDs
- System automatically uses fuzzy matching for these
- Check email addresses for additional verification

## Contributing

This is part of a larger evaluation system. For contributions:
1. Follow the existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure caching works correctly with your changes

## License

See the main project LICENSE file.

## Related Documentation

- [Main Project README](../README.md)
- [Webapp Documentation](../webapp/README.md)
- [Audit Tools](../audit/README.md)
