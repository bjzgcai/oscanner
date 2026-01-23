# Benchmark & Validation System

## Overview

This validation framework provides automated testing of the Engineer Capability Assessment System using a curated dataset of 50+ benchmark repositories with known characteristics.

## Components

### 1. Benchmark Dataset (`benchmark_dataset.py`)

A curated collection of **60+ test repositories** organized by category:

- **Ground Truth** (2 repos): Manually constructed repos with known skill levels
- **Famous Developers** (5 repos): Well-known OSS contributors (Linus, Evan You, Dan Abramov, etc.)
- **Dimension Specialists** (18 repos): Experts in specific dimensions (AI, Cloud, OSS, etc.)
- **Rising Stars** (3 repos): Mid-level to senior developers
- **Temporal Evolution** (2+ repos): Same developer at different time periods
- **Edge Cases** (5+ repos): Small repos, docs-heavy, solo developers
- **Corporate/Team** (2+ repos): Large team projects
- **Domain Specialists** (3+ repos): Security, visualization, systems
- **International** (1+ repos): Non-English developers
- **Comparison Pairs** (4+ repos): Known relative rankings

Each test repository includes:
- Expected skill level
- Expected score range
- Strong/weak dimensions
- Category metadata
- Public reputation notes

### 2. Validators (`validators.py`)

Five validation strategies:

#### ConsistencyValidator
- **Purpose**: Test score stability across multiple runs
- **Target**: Variance < 5 points across 3 evaluations
- **Pass Criteria**: 90% of repos show consistent scores

#### CorrelationValidator
- **Purpose**: Compare actual vs expected scores
- **Target**: Pearson correlation r > 0.7 with ground truth
- **Pass Criteria**: Correlation > 0.7 OR 80% within expected range

#### DimensionValidator
- **Purpose**: Verify dimension-specific expectations
- **Target**: Strong dimensions score > 75, weak < 60
- **Pass Criteria**: 70% of dimension expectations match

#### TemporalValidator
- **Purpose**: Verify growth over time for same developer
- **Target**: Later work scores > earlier work by 10+ points
- **Pass Criteria**: 80% show growth trajectory

#### OrderingValidator
- **Purpose**: Verify skill level ordering
- **Target**: Expert > Architect > Senior > Intermediate > Novice
- **Pass Criteria**: All orderings correct

### 3. Validation Runner (`validation_runner.py`)

Orchestrates validation tests:
- Evaluates benchmark repos (with caching)
- Runs all validators
- Aggregates results
- Saves detailed reports
- Provides summary statistics

### 4. Human Validation Protocol (`HUMAN_VALIDATION_PROTOCOL.md`)

Complete protocol for expert validation study:
- Participant recruitment (10-15 experts)
- Test set design (20 repos)
- Rating interface specifications
- Statistical analysis methods
- Publication strategy

## Usage

### CLI Tool

```bash
# Show dataset statistics
python evaluator/validation/run_validation.py --stats

# List all categories
python evaluator/validation/run_validation.py --list-categories

# List all benchmark repos
python evaluator/validation/run_validation.py --list-repos

# List previous validation runs
python evaluator/validation/run_validation.py --list-runs

# Show details of a specific run
python evaluator/validation/run_validation.py --show-run 20260123_143022
```

### API Endpoints

#### Get Dataset Info

```bash
GET /api/benchmark/dataset
```

Response:
```json
{
  "success": true,
  "stats": {
    "total": 60,
    "ground_truth": 2,
    "categories": 10,
    "expert": 35
  },
  "categories": ["ground_truth", "famous_developer", ...]
}
```

#### Get Benchmark Repos

```bash
GET /api/benchmark/repos?category=famous_developer
```

Response:
```json
{
  "success": true,
  "repos": [
    {
      "platform": "github",
      "owner": "torvalds",
      "repo": "linux",
      "author": "torvalds",
      "category": "famous_developer",
      "skill_level": "expert",
      "expected_score_range": [90, 98],
      "strong_dimensions": ["leadership", "open_source"],
      "description": "Creator of Linux kernel"
    }
  ]
}
```

#### Run Validation

```bash
POST /api/benchmark/validate
Content-Type: application/json

{
  "subset": "ground_truth",  # Optional: test specific category
  "quick_mode": true          # Optional: skip consistency test
}
```

Response:
```json
{
  "success": true,
  "run_id": "20260123_143022",
  "overall_passed": true,
  "overall_score": 85.5,
  "validation_results": [
    {
      "test_name": "Correlation Test",
      "passed": true,
      "score": 76.0,
      "details": {...}
    }
  ]
}
```

#### List Validation Runs

```bash
GET /api/benchmark/validation/runs
```

#### Get Validation Run Details

```bash
GET /api/benchmark/validation/runs/20260123_143022
```

#### Evaluate Single Benchmark Repo

```bash
GET /api/benchmark/repo/github/torvalds/linux/torvalds?use_cache=true
```

### Python API

```python
from evaluator.validation.benchmark_dataset import benchmark_dataset
from evaluator.validation.validation_runner import ValidationRunner

# Get dataset info
stats = benchmark_dataset.get_stats()
print(f"Total repos: {stats['total']}")

# Get repos by category
famous_devs = benchmark_dataset.get_by_category("famous_developer")

# Get dimension specialists
ai_specialists = benchmark_dataset.get_dimension_specialists(DimensionStrength.AI_MODEL)

# Run validation (requires async context)
async def run_validation():
    runner = ValidationRunner(
        dataset=benchmark_dataset,
        evaluation_function=your_eval_function
    )

    result = await runner.run_full_validation(
        subset="ground_truth",
        quick_mode=True
    )

    print(f"Overall: {'PASS' if result.overall_passed else 'FAIL'}")
    print(f"Score: {result.overall_score:.1f}/100")

    return result

# Run it
import asyncio
asyncio.run(run_validation())
```

## Validation Workflow

### 1. Initial Setup

```bash
# Start the evaluator server
cd evaluator
python server.py
```

### 2. Run Quick Validation

Test on a small subset first:

```bash
curl -X POST http://localhost:8000/api/benchmark/validate \
  -H 'Content-Type: application/json' \
  -d '{"subset": "ground_truth", "quick_mode": true}'
```

### 3. Run Full Validation

```bash
curl -X POST http://localhost:8000/api/benchmark/validate \
  -H 'Content-Type: application/json' \
  -d '{"quick_mode": false}'
```

This will:
- Evaluate all 60+ benchmark repos
- Run all 5 validators
- Generate detailed report
- Save results to `~/.local/share/oscanner/validation_cache/runs/`

### 4. Review Results

```python
python evaluator/validation/run_validation.py --list-runs
python evaluator/validation/run_validation.py --show-run 20260123_143022
```

Or via API:

```bash
curl http://localhost:8000/api/benchmark/validation/runs
```

## Expected Results

### Target Metrics

| Validator | Target | Good | Excellent |
|-----------|--------|------|-----------|
| Consistency | Variance < 5 | 90% pass | 95% pass |
| Correlation | r > 0.70 | r > 0.75 | r > 0.80 |
| Dimension | 70% match | 75% match | 85% match |
| Temporal | 80% growth | 85% growth | 90% growth |
| Ordering | All correct | All correct | All correct |

### Interpretation

**Overall Score 80-100**: Excellent validation
- High correlation with expert expectations
- Consistent scoring across runs
- Dimension assessments accurate

**Overall Score 60-79**: Good validation
- Moderate correlation
- Some inconsistencies
- Most dimensions accurate

**Overall Score < 60**: Needs improvement
- Low correlation with expectations
- High variance
- Dimension mismatches

## Adding New Test Repos

To add repositories to the benchmark dataset:

1. Edit `evaluator/validation/benchmark_dataset.py`
2. Add to the appropriate category in `_init_dataset()`:

```python
TestRepository(
    platform="github",
    owner="your-org",
    repo="your-repo",
    author="contributor-name",
    skill_level=SkillLevel.SENIOR,
    expected_score_range=(75, 85),
    strong_dimensions=[DimensionStrength.CLOUD_NATIVE],
    category="your_category",
    description="Brief description",
    is_ground_truth=False  # True if manually verified
)
```

3. Re-run validation to include the new repo

## Caching

Evaluation results are cached in:
```
~/.local/share/oscanner/validation_cache/
├── github_owner_repo_author.json   # Individual repo evaluations
└── runs/
    └── 20260123_143022.json        # Validation run results
```

To clear cache:
```bash
rm -rf ~/.local/share/oscanner/validation_cache/
```

## Human Validation Study

See [HUMAN_VALIDATION_PROTOCOL.md](./HUMAN_VALIDATION_PROTOCOL.md) for complete protocol to conduct expert validation study.

Quick start:
1. Recruit 10+ expert raters
2. Build rating interface (see protocol)
3. Collect ratings
4. Run statistical analysis:
   - Inter-rater reliability (ICC)
   - System-expert correlation
   - Agreement rates

Target: r > 0.75 correlation with expert ratings

## Troubleshooting

### Issue: Validation fails with "No evaluation function"

**Solution**: The validation runner needs an evaluation function. When running via API, this is automatically provided. When running standalone, you need to provide one.

### Issue: Rate limiting errors

**Solution**:
- Set `GITHUB_TOKEN` environment variable
- Use `quick_mode=true` to reduce evaluations
- Test on smaller subsets first

### Issue: Low correlation scores

**Solution**:
- Check if expected ranges are realistic
- Review evaluation prompt quality
- Analyze which categories fail
- Consider adjusting dimension weights

### Issue: High variance in consistency test

**Solution**:
- Check LLM temperature settings (should be low)
- Verify cache is working
- Ensure evaluation context is stable

## Next Steps

1. **Run initial validation**: Test current system performance
2. **Analyze results**: Identify weak areas
3. **Iterate**: Refine prompts, adjust weights
4. **Human study**: Conduct expert validation
5. **Publish**: Share results publicly

## Files

```
evaluator/validation/
├── __init__.py                      # Package exports
├── benchmark_dataset.py             # 60+ curated test repos
├── validators.py                    # 5 validation strategies
├── validation_runner.py             # Orchestration logic
├── run_validation.py                # CLI tool
├── HUMAN_VALIDATION_PROTOCOL.md     # Expert study protocol
└── README.md                        # This file
```

## Related Documentation

- [Main README](../../README.md) - Project overview
- [Human Validation Protocol](./HUMAN_VALIDATION_PROTOCOL.md) - Expert study design
- [API Documentation](http://localhost:8000/docs) - Interactive API docs

## Contributing

To contribute test repositories:
1. Fork the repo
2. Add test repos to `benchmark_dataset.py`
3. Document expected characteristics
4. Submit PR with validation results

## License

Same as parent project.
