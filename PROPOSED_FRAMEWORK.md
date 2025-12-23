# Revised Evaluation Framework for Domain Scientists in AI

## Target Audience
First-year PhD students transitioning from **biology, chemistry, medicine** to **AI-oriented research projects**

## Core Philosophy
Evaluate **engineering fundamentals for the AI era**, not professional software engineering. Focus on:
- Learning trajectory (not mastery)
- Research reproducibility (not production systems)
- Practical AI tool usage (not framework development)
- Domain integration (not pure CS)

---

## Six Evaluation Dimensions

### 1. AI Tools & Framework Proficiency (0-100)
**What**: Ability to use modern AI/ML tools and frameworks effectively

**Evaluate from commits:**
- ML framework usage (PyTorch, TensorFlow, scikit-learn, Hugging Face)
- Library choices and correct usage patterns
- Model loading, fine-tuning, and inference code
- Use of pre-trained models and transfer learning
- Integration of AI tools (LangChain, OpenAI API, etc.)

**Good indicators:**
```python
# Uses modern frameworks correctly
from transformers import AutoModel, AutoTokenizer
model = AutoModel.from_pretrained("bert-base-uncased")

# Proper data handling with PyTorch
from torch.utils.data import DataLoader
loader = DataLoader(dataset, batch_size=32, shuffle=True)
```

**Red flags:**
- Reinventing existing functionality
- Outdated or deprecated APIs
- Misuse of framework features

---

### 2. Code Quality & Reproducibility (0-100)
**What**: Writing clean, understandable, reproducible code for research

**Evaluate from commits:**
- Code readability and structure
- Meaningful variable/function names
- Comments and documentation
- Requirements.txt / environment.yml files
- Random seed setting for reproducibility
- Configuration management
- README files with setup instructions

**Good indicators:**
```python
# Clear, reproducible code
import random
import numpy as np
import torch

def set_seed(seed=42):
    """Set random seed for reproducibility"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

# Well-documented function
def preprocess_protein_sequence(sequence, max_length=512):
    """
    Preprocess protein sequence for BERT model.

    Args:
        sequence: Raw amino acid sequence
        max_length: Maximum sequence length
    Returns:
        Tokenized and padded sequence
    """
```

**Red flags:**
- Single-letter variables everywhere
- No comments or documentation
- Hardcoded paths and parameters
- No reproducibility considerations

---

### 3. Data Engineering & Management (0-100)
**What**: Handling datasets, preprocessing, and data pipelines for AI/ML

**Evaluate from commits:**
- Data loading and preprocessing scripts
- Data validation and cleaning
- Dataset splitting (train/val/test)
- Data augmentation techniques
- Handling different data formats (CSV, JSON, images, sequences)
- Data versioning awareness
- Efficient data loading (generators, batching)

**Good indicators:**
```python
# Proper data pipeline
class BiologyDataset(Dataset):
    def __init__(self, data_path, transform=None):
        self.data = pd.read_csv(data_path)
        self.transform = transform

    def __getitem__(self, idx):
        sample = self.data.iloc[idx]
        # Clear preprocessing logic
        processed = self.preprocess(sample)
        return processed

# Train/val/test split
from sklearn.model_selection import train_test_split
train, test = train_test_split(data, test_size=0.2, random_state=42)
```

**Red flags:**
- Data leakage (test data in training)
- No validation split
- Poor handling of missing data
- Loading entire dataset into memory unnecessarily

---

### 4. Version Control & Collaboration (0-100)
**What**: Effective use of Git and collaborative development practices

**Evaluate from commits:**
- Commit message quality (clear, descriptive)
- Logical commit organization (atomic commits)
- .gitignore usage (not committing data/models)
- Branch usage (if applicable)
- Issue/PR references
- Code review participation
- Handling of merge conflicts

**Good indicators:**
```
feat: add protein sequence tokenizer for BERT model

- Implement custom tokenizer for amino acid sequences
- Add padding and truncation logic
- Include unit tests for edge cases

Fixes #23
```

**Red flags:**
```
update
fix
changes
asdfasdf
final version
final final version
```
- Committing large data files or model weights
- No .gitignore file
- Binary files in repository

---

### 5. Experiment Tracking & Documentation (0-100)
**What**: Systematic experiment management and documentation

**Evaluate from commits:**
- Jupyter notebooks with clear narrative
- Experiment tracking (MLflow, Weights & Biases, or manual logs)
- Parameter logging and configuration files
- Results documentation (metrics, plots, tables)
- Model checkpointing
- Experiment versioning
- Lab notebook style documentation

**Good indicators:**
```python
# Experiment tracking
import wandb

wandb.init(project="protein-classification", config={
    "learning_rate": 0.001,
    "epochs": 50,
    "batch_size": 32,
    "model": "bert-base"
})

for epoch in range(epochs):
    loss = train_epoch()
    wandb.log({"loss": loss, "epoch": epoch})
```

**Notebooks with:**
- Clear markdown sections explaining each step
- Visualizations of results
- Documented findings and observations

**Red flags:**
- No experiment tracking at all
- Notebooks without markdown/explanations
- Can't reproduce experiments from code
- No logging of hyperparameters or metrics

---

### 6. Domain-AI Integration (0-100)
**What**: Effectively applying AI to domain-specific problems (biology/chemistry/medicine)

**Evaluate from commits:**
- Domain-specific data handling (protein sequences, molecular structures, medical images)
- Use of domain-specific libraries (BioPython, RDKit, MedPy, etc.)
- Domain-aware preprocessing
- Biologically/chemically/medically meaningful features
- Domain-specific evaluation metrics
- Understanding of domain constraints
- Literature/method references in comments

**Good indicators:**
```python
# Domain-aware code
from Bio import SeqIO
from rdkit import Chem
from sklearn.metrics import roc_auc_score  # Appropriate for medical diagnosis

# Processing protein data with domain knowledge
def calculate_protein_features(sequence):
    """Extract biologically relevant features from protein sequence"""
    features = {
        'hydrophobicity': calculate_hydrophobicity(sequence),
        'charge': calculate_net_charge(sequence),
        'secondary_structure': predict_secondary_structure(sequence)
    }
    return features
```

**Red flags:**
- Treating domain data as generic data without understanding
- Ignoring domain-specific requirements
- Using inappropriate metrics for domain
- No domain-specific validation

---

## Scoring Guidelines

### Score Ranges
- **80-100**: Excellent - Professional research engineering quality
- **60-79**: Good - Solid understanding, minor improvements needed
- **40-59**: Developing - Basic competence, needs guidance
- **20-39**: Beginner - Learning fundamentals, requires significant support
- **0-19**: Minimal - Limited evidence of skills

### Level Expectations for First-Year PhD Students

**Expected Range: 40-70 across most dimensions**

Early in PhD (Months 1-6):
- AI Tools: 30-50 (learning frameworks)
- Code Quality: 40-60 (developing habits)
- Data Engineering: 35-55 (understanding pipelines)
- Version Control: 30-50 (learning Git)
- Experiment Tracking: 25-45 (establishing practices)
- Domain Integration: 50-70 (strong domain knowledge, learning AI application)

Mid First-Year (Months 6-12):
- AI Tools: 50-70 (comfortable with frameworks)
- Code Quality: 55-70 (good practices established)
- Data Engineering: 50-65 (solid pipelines)
- Version Control: 50-70 (regular Git usage)
- Experiment Tracking: 45-65 (systematic tracking)
- Domain Integration: 60-80 (effectively combining domain + AI)

---

## Key Differences from Original Framework

| Original (Software Engineering) | Revised (Domain Science PhD) |
|--------------------------------|------------------------------|
| AI Model Development & Deployment | AI Tools & Framework Proficiency |
| Microservices & Architecture | Code Quality & Reproducibility |
| Cloud Native & Kubernetes | Data Engineering & Management |
| Open Source Leadership | Version Control & Collaboration |
| Advanced CI/CD Automation | Experiment Tracking & Documentation |
| Engineering Leadership | Domain-AI Integration |

**Focus shift:**
- From production → research
- From building systems → using tools
- From architecture → reproducibility
- From deployment → experimentation
- From leadership → learning

---

## Implementation Notes

### What Can Be Detected from GitHub Commits

✅ **Easily detectable:**
- Framework imports and usage
- Code structure and comments
- Data loading patterns
- Commit message quality
- File organization (.gitignore, requirements.txt)
- Notebook structure (if committed)

⚠️ **Partially detectable:**
- Experiment tracking (if code is in commits)
- Domain integration (from code context)
- Reproducibility (from code patterns)

❌ **Hard to detect:**
- Actual experiment results (unless logged in repo)
- Code that wasn't committed
- Knowledge not reflected in code

### Recommended Analysis Approach

For each dimension, the LLM should:
1. **Scan commits** for relevant code patterns
2. **Count evidence** (framework usage, good practices, etc.)
3. **Assess quality** (not just presence, but correctness)
4. **Consider trajectory** (improvement over time)
5. **Provide specific examples** from commits
6. **Score 0-100** with reasoning

---

## Example Evaluation Output

```json
{
  "username": "biology_phd_student",
  "total_commits_analyzed": 45,
  "scores": {
    "ai_tools_proficiency": 62,
    "code_quality": 58,
    "data_engineering": 55,
    "version_control": 48,
    "experiment_tracking": 52,
    "domain_integration": 71,
    "overall_assessment": "Developing researcher with strong domain knowledge, actively learning AI engineering fundamentals"
  },
  "dimension_analysis": {
    "ai_tools_proficiency": {
      "score": 62,
      "evidence": [
        "Uses PyTorch and Hugging Face transformers (15 commits)",
        "Proper model loading and fine-tuning patterns",
        "Some use of scikit-learn for preprocessing"
      ],
      "improvements": [
        "Could use more data augmentation libraries",
        "Limited use of modern experiment tracking tools"
      ]
    },
    "domain_integration": {
      "score": 71,
      "evidence": [
        "Extensive use of BioPython for sequence analysis",
        "Domain-specific feature engineering (hydrophobicity, secondary structure)",
        "Appropriate biological evaluation metrics"
      ],
      "improvements": [
        "Could add more biological validation steps"
      ]
    }
  }
}
```

---

## Next Steps

1. **Update system prompt** in commit_evaluator.py with new criteria
2. **Modify scoring logic** to match PhD student expectations
3. **Update dashboard UI** to show new dimension names
4. **Adjust LLM prompt** to focus on learning trajectory
5. **Test with sample repos** from biology/chemistry/medicine backgrounds

Would you like me to proceed with implementing these changes?
