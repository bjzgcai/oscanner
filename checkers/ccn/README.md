# Cyclomatic Complexity Checker (CCN)

This checker analyzes the cyclomatic complexity of functions in Python files using the `lizard` tool.

## Usage

Add `/checker:ccn` to your commit message to trigger this checker.

Example:
```
feat: add new feature

/checker:ccn
```

## Configuration

- **Threshold**: 20 (maximum allowed cyclomatic complexity)
- **Language**: Python only

## Output

The checker returns:
- `success`: Whether the check completed successfully
- `score`: Percentage of functions that passed (0-100)
- `passed`: Number of functions with complexity <= threshold
- `total`: Total number of functions analyzed
- `details`: List of function details with complexity scores
- `message`: Human-readable summary

## Installation

Install the required dependency:
```bash
pip install lizard
```

## Extending

To modify the threshold or add support for other languages, edit `checker.py` and update the `threshold` variable or add additional file type checks.
