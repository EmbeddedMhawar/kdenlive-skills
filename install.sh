#!/usr/bin/env bash
set -e

PLUGIN_NAME="kdenlive"
PLUGIN_DIR="${HOME}/.gemini/config/plugins/${PLUGIN_NAME}"
REPO_URL="https://github.com/EmbeddedMhawar/kdenlive-skills.git"

echo "============================================================"
echo "  Google Antigravity: Kdenlive Video Suite Plugin Installer"
echo "============================================================"

if [ -d "$PLUGIN_DIR" ]; then
  echo "==> Existing installation detected at ${PLUGIN_DIR}."
  echo "==> Pulling latest updates..."
  cd "$PLUGIN_DIR"
  git pull --quiet origin main || true
  echo "✅ Successfully updated to the latest version!"
else
  echo "==> Installing plugin to ${PLUGIN_DIR}..."
  mkdir -p "$(dirname "$PLUGIN_DIR")"
  git clone --depth 1 "$REPO_URL" "$PLUGIN_DIR"
  echo "✅ Installation complete!"
fi

echo ""
echo "🎬 6 Professional Kdenlive video editing workflows are active in Antigravity:"
echo "   - kdenlive-rough-cut        (Automated rough cuts & retake pruning)"
echo "   - kdenlive-zoom-cuts        (Semantic transcript-driven zoom cuts)"
echo "   - kdenlive-motion-graphics  (Kinetic titles, chapter cards & motion SFX)"
echo "   - kdenlive-broll-inserts    (B-roll cataloging & Track V2 placement)"
echo "   - kdenlive-redundancy-pruner (Proposition collisions & deduplication)"
echo "   - kdenlive-transcript-sfx   (Transcript-driven Foley & Minecraft SFX)"
echo ""
echo "   Try prompting Antigravity with:"
echo "   - 'Rough cut this raw video for Kdenlive: /path/to/video.mp4'"
echo "   - 'Apply semantic zoom cuts to project_roughcut.kdenlive'"
echo "   - 'Add transcript-driven sound effects and Minecraft SFX'"
echo "============================================================"
