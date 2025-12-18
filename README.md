# Engineer Capability Assessment System

A comprehensive system for evaluating engineer capabilities based on GitHub and Gitee activity analysis, using a six-dimensional evaluation framework.

## Overview

This system analyzes engineering activity from version control platforms (GitHub, Gitee) and generates a multi-dimensional capability assessment for software engineers.

## Six-Dimensional Evaluation Framework

### 1. AI Model Full-Stack & Trade-off Capability (AI模型全栈与权衡能力)
**Focus Areas:** Research-production mutual promotion innovation, system optimization
- Deep learning framework usage and optimization
- Model selection and trade-off decisions
- End-to-end AI system implementation

### 2. AI Native Architecture & Communication Design (AI原生架构与沟通设计)
**Focus Areas:** Production-level platform, research-production mutual promotion innovation
- AI-first architecture design
- API and interface design for AI systems
- Documentation and communication patterns

### 3. Cloud Native & Constraint Engineering (云原生与约束工程化)
**Focus Areas:** Production-level platform, system optimization
- Containerization and orchestration
- Infrastructure as code
- CI/CD pipeline implementation
- Resource optimization and constraints

### 4. Open Source Collaboration & Requirements Translation (开源协作与需求转化)
**Focus Areas:** Open source co-construction, research-production mutual promotion innovation
- Open source contribution quality and frequency
- Issue management and PR reviews
- Requirements analysis and implementation

### 5. Intelligent Development & Human-Machine Collaboration (智能开发与人机协同)
**Focus Areas:** All specialties
- AI-assisted development practices
- Code generation and review
- Automation and tooling

### 6. Engineering Leadership & System Trade-offs (工程领导与系统权衡)
**Focus Areas:** System optimization, production-level platform, research-production mutual promotion innovation
- Technical decision making
- System architecture trade-offs
- Team collaboration and mentorship

## Input

- GitHub account names
- Gitee account names
- Repository URLs (individual, pair programming, team projects)

## Output

- Six-dimensional scores (0-100 scale)
- Strengths and weaknesses analysis
- Detailed capability report
- Improvement recommendations

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Copy the example configuration file and update with your credentials:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your GitHub and Gitee API tokens.

## Usage

### Basic Usage

```python
from evaluator import EngineerEvaluator

evaluator = EngineerEvaluator()

# Evaluate a single engineer
result = evaluator.evaluate(
    github_username="username",
    gitee_username="username",
    repos=[
        "https://github.com/org/project1",
        "https://gitee.com/org/project2"
    ]
)

# Print report
print(result.get_report())
```

### CLI Usage

```bash
# Evaluate from configuration file
python main.py --config engineer_profile.yaml

# Evaluate with direct parameters
python main.py --github-user username --gitee-user username --repos repo1,repo2

# Generate detailed report
python main.py --config engineer_profile.yaml --output-format json --output report.json
```

## Project Structure

```
.
├── README.md
├── requirements.txt
├── config.example.yaml
├── main.py
├── evaluator/
│   ├── __init__.py
│   ├── core.py              # Main evaluation engine
│   ├── dimensions.py        # Six dimension evaluators
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── github.py        # GitHub data collection
│   │   └── gitee.py         # Gitee data collection
│   ├── analyzers/
│   │   ├── __init__.py
│   │   ├── code_analyzer.py
│   │   ├── commit_analyzer.py
│   │   └── collaboration_analyzer.py
│   └── reporters/
│       ├── __init__.py
│       ├── text_reporter.py
│       └── json_reporter.py
├── tests/
│   └── __init__.py
└── examples/
    └── sample_evaluation.py
```

## Data Sources

The system collects and analyzes:

- **Commit History:** Frequency, quality, patterns
- **Code Review:** PR reviews, feedback quality
- **Issue Management:** Issue creation, resolution, communication
- **Repository Structure:** Architecture patterns, technology choices
- **Documentation:** README, comments, API docs
- **Collaboration:** Team interactions, mentorship indicators
- **Technology Stack:** Languages, frameworks, tools
- **CI/CD:** Pipeline configurations, automation

## Scoring Methodology

Each dimension is scored based on weighted indicators:

- **Quantitative Metrics:** Commit frequency, PR count, code volume
- **Qualitative Analysis:** Code quality, architecture decisions, documentation
- **Collaboration Patterns:** Review quality, issue resolution, team engagement
- **Innovation Indicators:** Novel solutions, technology adoption, experimentation

## Development

### Running Tests

```bash
pytest tests/
```

### Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## License

MIT License

## Roadmap

- [ ] GitLab support
- [ ] Enhanced AI/ML project detection
- [ ] Team-level analytics
- [ ] Historical trend analysis
- [ ] Benchmarking against industry standards
- [ ] Visual dashboard
