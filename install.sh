#!/usr/bin/env bash
# -------------------------------------------------------------------
# Weekly Monitor — one-command installer (macOS / Linux)
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
echo "  ╔═══════════════════════════════════╗"
echo "  ║   Weekly Monitor — Installer      ║"
echo "  ╚═══════════════════════════════════╝"
echo ""

# ── Step 1: Find or install Python 3.11+ ─────────────────────────
find_python() {
    for cmd in python3.12 python3.11 python3 python; do
        if command -v "$cmd" &>/dev/null; then
            version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON=""
if PYTHON=$(find_python); then
    echo "  [1/4] Found $($PYTHON --version)"
else
    echo "  [1/4] Python 3.11+ not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS — try Homebrew
        if command -v brew &>/dev/null; then
            echo "        Using Homebrew to install Python 3.12..."
            brew install python@3.12
        else
            echo "        Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)"
            brew install python@3.12
        fi
    elif command -v apt-get &>/dev/null; then
        # Debian / Ubuntu
        echo "        Using apt to install Python 3.12..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq python3.12 python3.12-venv python3-pip
    elif command -v dnf &>/dev/null; then
        # Fedora / RHEL
        echo "        Using dnf to install Python 3.12..."
        sudo dnf install -y python3.12
    elif command -v pacman &>/dev/null; then
        # Arch
        echo "        Using pacman to install Python..."
        sudo pacman -S --noconfirm python
    else
        echo ""
        echo "  ERROR: Cannot auto-install Python on this system."
        echo "  Please install Python 3.11+ manually from:"
        echo "    https://www.python.org/downloads/"
        echo ""
        exit 1
    fi

    # Re-check
    if PYTHON=$(find_python); then
        echo "        Installed $($PYTHON --version)"
    else
        echo ""
        echo "  ERROR: Python installation failed."
        echo "  Please install Python 3.11+ manually from:"
        echo "    https://www.python.org/downloads/"
        echo ""
        exit 1
    fi
fi

# ── Step 2: Clone or update repo ──────────────────────────────────
echo "  [2/4] Getting source code..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "        Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "        Cloning repository..."
    git clone --progress "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# ── Step 3: Create venv + install dependencies ────────────────────
echo "  [3/4] Installing Python dependencies..."
if [ ! -d ".venv" ]; then
    "$PYTHON" -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install .

# ── Step 4: Install Chromium ──────────────────────────────────────
echo "  [4/4] Installing Chromium browser for screenshots..."
.venv/bin/python -m playwright install chromium

# ── Done ──────────────────────────────────────────────────────────
BINDIR="$INSTALL_DIR/.venv/bin"
echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   Installation complete!                  ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""
echo "  Run the monitor:"
echo ""
echo "    $BINDIR/weekly-monitor interactive"
echo ""
echo "  Add to your shell profile for easy access:"
echo ""
echo "    alias weekly-monitor='$BINDIR/weekly-monitor'"
echo ""
