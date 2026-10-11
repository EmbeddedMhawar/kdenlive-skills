#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="${REPO_DIR}/skills"

echo "==> Validating Antigravity Kdenlive Skills in ${SKILLS_DIR}..."
ERRORS=0
TOTAL=0

for skill_path in "${SKILLS_DIR}"/*; do
  if [ -d "$skill_path" ]; then
    skill_name=$(basename "$skill_path")
    skill_file="${skill_path}/SKILL.md"
    TOTAL=$((TOTAL + 1))

    if [ ! -f "$skill_file" ]; then
      echo "❌ Error: Missing SKILL.md in $skill_path"
      ERRORS=$((ERRORS + 1))
      continue
    fi

    # Check for frontmatter marker
    if ! head -n 1 "$skill_file" | grep -q "^---"; then
      echo "❌ Error: Missing starting '---' YAML frontmatter in $skill_name"
      ERRORS=$((ERRORS + 1))
      continue
    fi

    # Check for name and description
    if ! grep -q "^name:" "$skill_file"; then
      echo "❌ Error: Missing 'name:' field in $skill_name frontmatter"
      ERRORS=$((ERRORS + 1))
      continue
    fi

    if ! grep -q "^description:" "$skill_file"; then
      echo "❌ Error: Missing 'description:' field in $skill_name frontmatter"
      ERRORS=$((ERRORS + 1))
      continue
    fi

    echo "  ✅ ${skill_name}"
  fi
done

echo ""
if [ $ERRORS -gt 0 ]; then
  echo "❌ Validation failed: ${ERRORS} error(s) found out of ${TOTAL} skills."
  exit 1
fi

echo "✨ All ${TOTAL} Kdenlive skills passed Antigravity validation successfully!"
exit 0
