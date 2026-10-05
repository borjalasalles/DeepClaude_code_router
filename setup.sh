#!/usr/bin/env bash
# setup.sh — one-shot install for deep-devops on a fresh machine.
#
# Usage:
#   cp .env.example .env          # fill in DEEPSEEK_API_KEY first
#   bash setup.sh
#   deep                          # launch the agent
set -euo pipefail

# ── 1. uv ────────────────────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "[1/6] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck source=/dev/null
    source "$HOME/.local/bin/env" 2>/dev/null || export PATH="$HOME/.local/bin:$PATH"
else
    echo "[1/6] uv already present ($(uv --version))"
fi

# ── 2. Project dependencies ──────────────────────────────────────────────────
echo "[2/6] Installing project dependencies (uv sync)..."
uv sync

# ── 3. deepagents CLI ────────────────────────────────────────────────────────
# Find the deepagents binary that supports --model (CLI 0.0.x interface).
# deepagents-cli 0.1.x changed to subcommands (init/dev/deploy) and is incompatible.
find_deepagents_bin() {
    local search_dirs=(
        "$HOME/.local/share/uv/tools/deepagents-cli/bin"
        "$HOME/snap/code/current/.local/share/uv/tools/deepagents-cli/bin"
    )
    for d in "$HOME"/snap/code/*/; do
        search_dirs+=("${d}.local/share/uv/tools/deepagents-cli/bin")
    done

    for dir in "${search_dirs[@]}"; do
        local bin="$dir/deepagents"
        if [ -x "$bin" ]; then
            local ver
            ver=$("$bin" --version 2>/dev/null | head -1 || true)
            if [[ "$ver" == deepagents-cli\ 0.0.* ]]; then
                echo "$bin"
                return 0
            fi
        fi
    done
    return 1
}

DEEPAGENTS_BIN=$(find_deepagents_bin || true)

if [ -z "$DEEPAGENTS_BIN" ]; then
    echo "[3/6] Installing deepagents CLI (0.0.x)..."
    curl -LsSf https://langch.in/gh-da-cli | bash
    DEEPAGENTS_BIN=$(find_deepagents_bin)
else
    echo "[3/6] deepagents CLI already installed ($("$DEEPAGENTS_BIN" --version 2>/dev/null | head -1))"
fi

DEEPAGENTS_PYTHON="$(dirname "$DEEPAGENTS_BIN")/python"

# ── 4. Install deep_devops into the deepagents environment ───────────────────
# The package must live in the deepagents isolated env, not just the project venv.
echo "[4/6] Installing deep-devops into deepagents env..."
uv pip install -e . --python "$DEEPAGENTS_PYTHON"

# ── 5. ~/.deepagents/ config and env ─────────────────────────────────────────
echo "[5/6] Configuring ~/.deepagents/ ..."
mkdir -p ~/.deepagents

if [ ! -f ~/.deepagents/config.toml ]; then
    cp deepagents_config.example.toml ~/.deepagents/config.toml
    echo "      Created ~/.deepagents/config.toml from example"
else
    echo "      ~/.deepagents/config.toml already exists — skipping (not overwritten)"
fi

if [ ! -f ~/.deepagents/.env ]; then
    echo "DEEPSEEK_API_KEY=" > ~/.deepagents/.env
    chmod 600 ~/.deepagents/.env
    echo "      Created ~/.deepagents/.env — add your key there"
else
    echo "      ~/.deepagents/.env already exists — skipping"
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "      Created .env from .env.example — add DEEPSEEK_API_KEY"
fi

# ── 6. `deep` command ────────────────────────────────────────────────────────
echo "[6/6] Installing 'deep' command..."
mkdir -p ~/.local/bin
cat > ~/.local/bin/deep << WRAPPER
#!/usr/bin/env bash
exec "$DEEPAGENTS_BIN" --model deep_devops:router "\$@"
WRAPPER
chmod +x ~/.local/bin/deep

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    export PATH="$HOME/.local/bin:$PATH"
    for rc in ~/.bashrc ~/.zshrc; do
        if [ -f "$rc" ] && ! grep -q '\.local/bin' "$rc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
            echo "      Added ~/.local/bin to PATH in $rc"
        fi
    done
fi
echo "      'deep' command ready → $DEEPAGENTS_BIN"

# ── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  1. Add your DeepSeek API key to BOTH files:"
echo "       .env                        (used by deep-devops router)"
echo "       ~/.deepagents/.env          (used by the deepagents CLI itself)"
echo ""
echo "  2. Launch:"
echo "       deep"
echo ""
echo "  Kill-switch (routes everything to EU/Anthropic, bypasses China tier):"
echo "       DEEP_DEVOPS_DISABLE_PUBLIC_TIER=1 deep"
