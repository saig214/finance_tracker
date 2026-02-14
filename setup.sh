#!/usr/bin/env bash
set -euo pipefail

# ─── One-shot setup: fresh clone → running state ───

echo "==> Finding Python >= 3.11..."

PYTHON=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" -c "import sys; print(f'{sys.version_info.minor}')" 2>/dev/null || echo "0")
    if [ "$ver" -ge 11 ]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "ERROR: Python >= 3.11 not found. Install it and re-run."
  exit 1
fi

echo "    Using $PYTHON ($($PYTHON --version))"

# ─── Virtual environment ───
if [ ! -d .venv ]; then
  echo "==> Creating .venv..."
  $PYTHON -m venv .venv
else
  echo "==> .venv already exists, skipping creation."
fi

source .venv/bin/activate

# ─── Install package ───
echo "==> Installing finance[dev] in editable mode..."
pip install -e ".[dev]" --quiet

# ─── Environment file ───
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "==> Copying .env.example → .env"
    cp .env.example .env
  else
    echo "==> No .env.example found, skipping .env creation."
  fi
else
  echo "==> .env already exists, skipping."
fi

# ─── Git hooks (PII scanner) ───
echo "==> Installing pre-commit hook (PII scanner)..."
if [ -d .git ]; then
  cp hooks/pre-commit .git/hooks/pre-commit
  chmod +x .git/hooks/pre-commit
  echo "    Installed .git/hooks/pre-commit"
else
  echo "    Not a git repo, skipping hook install."
fi

# ─── Data directories ───
echo "==> Creating data directories..."
mkdir -p data/db data/raw data/imports

# ─── Database migrations ───
echo "==> Running Alembic migrations..."
alembic upgrade head

# ─── Smoke test ───
echo "==> Smoke test: importing finance module..."
python -c "from finance.core.models import Transaction; print('    OK — finance module loads correctly')"

echo ""
echo "========================================="
echo "  Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  source .venv/bin/activate"
echo "  uvicorn finance.web.app:app --reload"
echo ""
echo "Edit .env to set PDF passwords and other secrets."
