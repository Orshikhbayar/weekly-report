#!/usr/bin/env bash
# -------------------------------------------------------------------
# Weekly Monitor — one-command installer
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/Orshikhbayar/weekly-report/main/install.sh | bash
#
# Or after cloning the repo:
#   bash install.sh
# -------------------------------------------------------------------
set -euo pipefail

REPO_URL="https://github.com/Orshikhbayar/weekly-report.git"
INSTALL_DIR="${WEEKLY_MONITOR_DIR:-$HOME/weekly-monitor}"

echo ""
echo "  Weekly Monitor — Installer"
echo "  ─────────────────────────────"
echo ""

# ── Step 1: Check Python ──────────────────────────────────────────
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  ERROR: Python 3.11+ is required but not found."
    echo "  Install it from https://www.python.org/downloads/"
    exit 1
fi
echo "  Found $($PYTHON --version)"

# ── Step 2: Clone or update repo ──────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Updating existing installation at $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo "  Cloning into $INSTALL_DIR..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── Step 3: Create venv + install ─────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

echo "  Installing dependencies..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet .

# ── Step 4: Install Chromium ──────────────────────────────────────
echo "  Installing Playwright Chromium browser..."
.venv/bin/python -m playwright install chromium

# ── Step 5: Create convenience alias ──────────────────────────────
BINDIR="$INSTALL_DIR/.venv/bin"
echo ""
echo "  ────────────────────────────────────────"
echo "  Installation complete!"
echo ""
echo "  To run the interactive monitor:"
echo ""
echo "    $BINDIR/weekly-monitor interactive"
echo ""
echo "  Or add this alias to your shell profile:"
echo ""
echo "    alias weekly-monitor='$BINDIR/weekly-monitor'"
echo ""
echo "  Then just run:"
echo ""
echo "    weekly-monitor interactive"
echo ""
echo "  ────────────────────────────────────────"
echo ""
