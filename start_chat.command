#!/bin/zsh
# Double-click in Finder to open Terminal in the agent's interactive chat.
# (If double-click does nothing, run once: chmod +x start_chat.command)

# Always work from this script's own folder, wherever it lives.
cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo "  🧬 Self-Evolving Agent — Interactive Chat"
echo "============================================================"

# Activate the project virtualenv if present.
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
fi

# Pick an interpreter.
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "❌ Python not found. Install Python 3.11+ and try again."
  echo "Press any key to close…"; read -k 1; exit 1
fi

DEFAULT_MODEL="gemma4:26b-mlx"
MODEL=""

# ── Model picker ───────────────────────────────────────────────
if curl -s --max-time 1 http://localhost:11434/api/tags >/dev/null 2>&1; then
  # Fetch installed model names (one per line), sorted.
  MODELS=("${(@f)$("$PY" - <<'PY'
import json, urllib.request
try:
    d = json.load(urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2))
    for m in sorted(x.get("name", "") for x in d.get("models", [])):
        if m:
            print(m)
except Exception:
    pass
PY
)}")

  if (( ${#MODELS} )); then
    echo "Installed Ollama models:"
    i=1
    for m in $MODELS; do
      tag=""
      [[ "$m" == *-mlx ]] && tag="  (MLX)"
      [[ "$m" == "$DEFAULT_MODEL" ]] && tag="$tag  [default]"
      printf "  %2d. %s%s\n" $i "$m" "$tag"
      i=$((i+1))
    done
    printf "\nPick a model [number or name, Enter = %s]: " "$DEFAULT_MODEL"
    read CHOICE

    if [[ -z "$CHOICE" ]]; then
      MODEL="$DEFAULT_MODEL"
    elif [[ "$CHOICE" == <-> ]] && (( CHOICE >= 1 && CHOICE <= ${#MODELS} )); then
      MODEL="${MODELS[$CHOICE]}"
    else
      MODEL="$CHOICE"   # a name or substring — demo.py resolves it
    fi
    echo "→ using: $MODEL"
  fi
else
  echo "⚠  Ollama isn't answering on localhost:11434."
  echo "   Start it ('ollama serve') for real answers, or continue (mock fallback)."
fi

echo ""
echo "Type a task and press Enter.  /help for commands,  /quit to exit."
echo ""

# ── Launch ─────────────────────────────────────────────────────
if [[ -n "$MODEL" ]]; then
  "$PY" demo.py --chat --provider ollama --model "$MODEL"
else
  "$PY" demo.py --chat --provider ollama
fi

# Keep the window open after the agent exits so output stays visible.
echo ""
echo "Session ended. Press any key to close this window…"
read -k 1
