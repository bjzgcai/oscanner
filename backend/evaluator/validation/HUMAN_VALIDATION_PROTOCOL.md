# Human Validation Experiment Protocol

## Overview

This document defines the protocol for conducting human expert validation of the Engineer Capability Assessment System. The goal is to measure how well the automated system's evaluations correlate with expert human judgment.

## Objectives

1. **Establish Validity**: Measure correlation between system scores and expert ratings (target: r > 0.7)
2. **Identify Biases**: Detect systematic over/under-scoring in specific dimensions
3. **Improve Accuracy**: Gather qualitative feedback to refine evaluation criteria
4. **Build Trust**: Publish results to demonstrate system reliability

## Study Design

### Participants

**Target: 10-15 Expert Raters**

**Inclusion Criteria:**
- Minimum 5 years professional software engineering experience
- Has hired or evaluated engineers in the past
- Experience with code review in production environments
- Diverse backgrounds (different companies, domains, tech stacks)

**Recruitment:**
- Personal network outreach
- Tech community forums (reddit.com/r/ExperiencedDevs, HackerNews)
- LinkedIn technical groups
- Open source maintainer communities

**Compensation:**
- $50 Amazon gift card per participant (1 hour commitment)
- Free premium access to oscanner for 1 year
- Co-authorship on published validation study (if desired)

### Test Set

**20 Carefully Selected Repositories** organized into 4 groups:

#### Group A: Ground Truth (5 repos)
- 1 Novice-level repo
- 1 Intermediate-level repo
- 1 Senior-level repo
- 2 Expert-level repos

**Purpose:** Establish baseline agreement on clear skill levels

#### Group B: Dimension Specialists (5 repos)
- 1 AI/ML specialist
- 1 Cloud native specialist
- 1 Open source leader
- 1 Tooling/DX specialist
- 1 Systems programming specialist

**Purpose:** Test dimension-specific scoring accuracy

#### Group C: Famous Developers (5 repos)
- Well-known OSS contributors with public reputation
- Examples: Evan You (Vue), Dan Abramov (Redux), TJ Holowaychuk

**Purpose:** Leverage public reputation as ground truth proxy

#### Group D: Edge Cases (5 repos)
- Very small repo (few commits)
- Documentation-heavy repo
- Solo developer project
- Corporate team project
- Temporal comparison (same dev, different periods)

**Purpose:** Test robustness in challenging scenarios

### Rating Interface

**Web-based Rating Form** (built as standalone page in webapp):

For each repository, raters see:
- Repository name and basic stats (commits, contributors, date range)
- Sample of 5-10 representative commits (with diffs)
- README and documentation snippets
- **NO system scores** (blind evaluation)

Raters provide:

1. **Overall Skill Level** (1-5 scale)
   - 1 = Novice (0-1 year equivalent)
   - 2 = Intermediate (2-3 years)
   - 3 = Senior (5+ years)
   - 4 = Architect (8+ years)
   - 5 = Expert (10+ years, thought leader)

2. **Six Dimension Scores** (0-100 scale)
   - AI Model Full-Stack & Trade-off
   - AI Native Architecture & Communication
   - Cloud Native Engineering
   - Open Source Collaboration
   - Intelligent Development
   - Engineering Leadership

   For each dimension:
   - Slider: 0-100
   - Optional text: "What evidence supports this score?"

3. **Confidence Rating** (1-5)
   - How confident are you in this evaluation?
   - 1 = Very uncertain, 5 = Very confident

4. **Optional Comments**
   - "Anything notable about this developer?"
   - Free-form text area

**Estimated time per repo:** 3-5 minutes
**Total time:** 60-90 minutes for all 20 repos

### Data Collection

**Database Schema:**

```sql
CREATE TABLE expert_ratings (
    id SERIAL PRIMARY KEY,
    rater_id VARCHAR(50),           -- Anonymized ID
    repo_identifier VARCHAR(200),   -- platform/owner/repo/author

    -- Overall rating
    skill_level INTEGER,            -- 1-5
    confidence INTEGER,             -- 1-5

    -- Dimension scores
    ai_model_score FLOAT,           -- 0-100
    ai_native_score FLOAT,
    cloud_native_score FLOAT,
    open_source_score FLOAT,
    intelligent_dev_score FLOAT,
    leadership_score FLOAT,

    -- Evidence
    ai_model_evidence TEXT,
    ai_native_evidence TEXT,
    cloud_native_evidence TEXT,
    open_source_evidence TEXT,
    intelligent_dev_evidence TEXT,
    leadership_evidence TEXT,

    -- Metadata
    comments TEXT,
    time_spent_seconds INTEGER,
    timestamp TIMESTAMP DEFAULT NOW(),

    -- Rater background
    rater_years_experience INTEGER,
    rater_industry VARCHAR(100),
    rater_primary_tech VARCHAR(100)
);

CREATE INDEX idx_expert_ratings_repo ON expert_ratings(repo_identifier);
CREATE INDEX idx_expert_ratings_rater ON expert_ratings(rater_id);
```

**Storage:**
- SQLite database: `~/.local/share/oscanner/validation/expert_ratings.db`
- Backup to JSON: Auto-export after each submission

## Study Procedure

### Phase 1: Pilot Test (Week 1)
1. Recruit 2 pilot participants
2. Have them complete rating interface
3. Debrief interview (15 min):
   - Was anything confusing?
   - Were commit samples sufficient?
   - How long did it take?
4. Revise protocol based on feedback

### Phase 2: Main Study (Week 2-3)
1. Recruit remaining 8-13 participants
2. Send each participant:
   - Study overview
   - Instructions document
   - Unique rating link
   - Consent form (anonymous data publication)
3. Participants complete ratings at their own pace
4. Send reminder after 3 days if incomplete

### Phase 3: Analysis (Week 4)

#### Quantitative Analysis

**1. Inter-Rater Reliability**
```python
# Calculate Intraclass Correlation Coefficient (ICC)
# Target: ICC > 0.75 (good agreement)
from scipy.stats import f_oneway

def calculate_icc(ratings_by_rater):
    # ratings_by_rater: dict[repo_id][rater_id] = score
    # ICC(2,k) - two-way random effects, average measures
    ...
```

**2. System-Expert Correlation**
```python
# For each dimension and overall score
from scipy.stats import pearsonr

system_scores = [...]  # From automated system
expert_avg_scores = [...]  # Average of all expert ratings

correlation, p_value = pearsonr(system_scores, expert_avg_scores)
# Target: r > 0.70 (strong correlation)
```

**3. Agreement Rate**
```python
# Percentage within ±10 points
within_range = sum(
    1 for s, e in zip(system_scores, expert_scores)
    if abs(s - e) <= 10
) / len(system_scores) * 100

# Target: > 70%
```

**4. Dimension Analysis**
- Which dimensions have highest agreement?
- Which have lowest? (may need refinement)
- Are there systematic biases? (system consistently higher/lower)

#### Qualitative Analysis

**Thematic Coding of Comments:**
1. What patterns do experts notice that system misses?
2. What does system overweight/underweight?
3. Suggestions for improvement

**Example themes:**
- "System doesn't recognize architectural contributions without code"
- "Solo projects undervalued in collaboration dimension"
- "Documentation quality not captured"

### Phase 4: Results Publication (Week 5)

**Academic Paper (arXiv preprint):**
- Title: "Automated Engineer Capability Assessment: A Validation Study"
- Sections: Introduction, Methods, Results, Discussion, Limitations
- Include all statistical measures
- Publish anonymized dataset

**Public Report (oscanner.dev/validation):**
- Executive summary of findings
- Key statistics (correlation, agreement rate)
- Interactive charts showing system vs expert scores
- Limitations and ongoing improvements
- Link to full paper

**Blog Post:**
- "How Accurate Is oscanner? We Asked 12 Expert Engineers"
- Narrative format, accessible to non-technical readers
- Include participant quotes (with permission)
- Honest about limitations

## Ethical Considerations

### Privacy
- Expert raters: Anonymized (Rater001, Rater002, etc.)
- Evaluated developers: Public repos only (no expectation of privacy)
- Ratings data: Aggregated for publication

### Consent
- Experts sign consent form allowing anonymous data publication
- Evaluated developers: Using publicly available commit data
- Clear disclosure that this is a research study

### Bias Mitigation
- Diverse rater pool (gender, geography, company size)
- Raters blinded to system scores
- Multiple raters per repo (reduces individual bias)

## Success Criteria

**Minimum Viable Validation:**
- ✅ n ≥ 10 expert raters
- ✅ Inter-rater reliability ICC > 0.6
- ✅ System-expert correlation r > 0.65
- ✅ Agreement rate > 60%

**Strong Validation:**
- ✅ n ≥ 12 expert raters
- ✅ Inter-rater reliability ICC > 0.75
- ✅ System-expert correlation r > 0.75
- ✅ Agreement rate > 70%
- ✅ No dimension with r < 0.5

**Exceptional Validation:**
- ✅ n ≥ 15 expert raters
- ✅ Inter-rater reliability ICC > 0.85
- ✅ System-expert correlation r > 0.80
- ✅ Agreement rate > 80%
- ✅ All dimensions r > 0.65

## Timeline

| Week | Activity | Deliverable |
|------|----------|-------------|
| 1 | Pilot test (n=2) | Revised protocol |
| 2-3 | Main study (n=10-13) | Rating database |
| 4 | Statistical analysis | Results report |
| 5 | Paper writing | arXiv preprint |
| 6 | Public release | Blog post, validation page |

## Budget

| Item | Cost |
|------|------|
| Participant compensation (12 × $50) | $600 |
| Survey platform (Typeform Pro, optional) | $0 (use own webapp) |
| Statistical software | $0 (Python/R, open source) |
| **Total** | **$600** |

## Implementation Checklist

### Technical Setup
- [ ] Create SQLite database for expert ratings
- [ ] Build rating interface page in webapp
- [ ] Generate unique rating links with rater IDs
- [ ] Implement progress tracking (X/20 repos completed)
- [ ] Auto-save drafts (prevent data loss)
- [ ] Export functionality (JSON backup)

### Study Materials
- [ ] Participant information sheet
- [ ] Consent form
- [ ] Rating instructions document
- [ ] Dimension definitions guide
- [ ] Email templates (invitation, reminder)

### Analysis Tools
- [ ] Python script: Calculate ICC
- [ ] Python script: System-expert correlation
- [ ] Python script: Generate comparison charts
- [ ] Jupyter notebook: Full analysis pipeline

### Publication
- [ ] LaTeX template for paper
- [ ] Validation results dashboard page
- [ ] Blog post draft
- [ ] Press kit (for media coverage)

## Future Iterations

After initial validation:

**Ongoing Validation (Quarterly):**
- New batch of 5-10 repos
- Same experts re-rate (track drift)
- Incorporate user feedback

**Expanded Studies:**
- Industry-specific validation (fintech vs gaming vs ML)
- Language-specific validation (Python vs Rust vs Go)
- Cross-cultural validation (US vs China vs Europe)

**User Feedback Loop:**
- "Rate this evaluation" feature in webapp
- Collect 1000+ user ratings
- Compare user ratings vs expert ratings vs system

## Contact

For questions about this protocol:
- Study coordinator: [Your Email]
- IRB/Ethics questions: [If applicable]
- Technical issues: [Support Email]

---

**Last Updated:** 2026-01-23
**Protocol Version:** 1.0
**Status:** Draft (Pending Pilot Test)
