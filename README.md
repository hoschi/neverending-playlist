# Supabase to Spotify

## Project Setup

### 1. Prerequisites
- [Conda](https://docs.conda.io/en/latest/miniconda.html) for environment management.
- [Poetry](https://python-poetry.org/docs/#installation) for package management.
- [Poe the Poet](https://poethepoet.natn.io/installation.html) for task management.

### 2. Installation

```bash
# Create and activate the conda environment
conda env create --file conda.yml
conda activate supabase-to-spotify

# Install dependencies using Poetry
poetry install

# add git filter for Jupyter notebooks
nbstripout --install
```

## Daily Work

### Running Quality Checks

This project is equipped with a comprehensive set of quality gates. To run them all locally, use the following commands:

```bash
# Run linter and formatter check
ruff check .
ruff format --check .

# Run static type checking
mypy

# Run tests and generate coverage reports
pytest

# Run all checks
poe check-all
```

To view the interactive coverage report after running the tests, open `htmlcov/index.html` in your browser.

### Interactive Documentation

The `docs/` directory contains interactive Jupyter Notebooks. They are the best way to learn the core concepts and patterns used in this project.

1.  **Open the project in VS Code.**
2.  **Make sure you have the recommended extensions installed (VS Code will prompt you).**
3.  **Select the project's Python interpreter: YOUR CONDA ENV.**
4.  **Open `docs/01_core_concepts.ipynb` or `docs/02_advanced_patterns.ipynb`.**
5.  **Run the code cells one by one to see the concepts in action.**

Each code cell ends with `assert` statements, making the documentation self-verifying.

## 🤖 Working with AI Assistants (Cursor, Gemini, etc.)

This project is specifically optimized to work with modern AI coding assistants. To ensure high code quality, we have created a "manifest" for AIs.

### Setup

Cursor and Gemini are already set up for you.

**For other tools:**
Explicitly include the main directive in your prompt. Example:
```bash
claude "Refactor the 'process_data' function in 'src/core/services.py'. Strictly follow the instructions from 'ai-assistants/01-main-directives.md'."
```

### The Rules

The `ai-assistants/` directory contains the complete set of rules. The AI is automatically referred to the relevant documents to ensure it always operates within the project's context.
