# Contributing to HVAC Control Center

Thanks for your interest in contributing. This doc explains what to do **first** so you can run the linter and tests locally (and have them run automatically before each commit).

## Prerequisites

- **Python 3.12+**
- **Git**

## First-time setup

Do these steps once per machine (or per clone).

### 1. Clone the repo

```bash
git clone https://github.com/thedeviousdev/ha-hvac-control-center.git
cd ha-hvac-control-center
```

(Or use your fork and add the upstream remote as needed.)

### 2. Install test dependencies

From the repo root:

```bash
pip install -r requirements_test.txt
```

This installs pytest, pytest-asyncio, Home Assistant, pytest-homeassistant-custom-component, pre-commit, and Ruff.

### 3. Install the pre-commit hooks

So that **Ruff** and **pytest** run automatically before every commit:

```bash
pre-commit install
```

After this, each `git commit` will:

1. Run `ruff check custom_components/ tests/`
2. Run `pytest tests/ -v --tb=short`

If either fails, the commit is blocked until you fix the issues.

### 4. (Optional) Run checks manually

- Lint:  
  `ruff check custom_components/ tests/ --output-format=github`

- Tests:  
  `pytest tests/ -v --tb=short`

- Run all pre-commit hooks (same as on commit):  
  `pre-commit run --all-files`

## Before you submit a PR

1. **Rebase on `main`** (or the current default branch) and fix any conflicts.
2. **Ensure pre-commit passes**  
   Run `pre-commit run --all-files` and fix any Ruff or pytest failures.
3. **Use conventional commits**  
   Prefer messages like `feat: ...`, `fix: ...`, `chore: ...`, `docs: ...` so Release Please can generate changelogs.

## Project layout

- **`custom_components/hvac_control_center/`** — Integration code (Python + frontend panel).
- **`tests/`** — Pytest tests (init, config flow, sensor).
- **`pyproject.toml`** — Pytest and Ruff config.
- **`.pre-commit-config.yaml`** — Pre-commit hooks (Ruff + pytest).

CI runs Ruff and pytest on pull requests; having pre-commit installed locally helps you catch the same issues before pushing.
