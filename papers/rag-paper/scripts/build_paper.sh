#!/usr/bin/env bash
set -euo pipefail
paper_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$paper_root"
if command -v latexmk >/dev/null 2>&1; then
  latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
elif command -v "${TECTONIC_BIN:-tectonic}" >/dev/null 2>&1; then
  "${TECTONIC_BIN:-tectonic}" --keep-logs --keep-intermediates --reruns 2 main.tex
else
  echo 'Install latexmk + XeLaTeX, or Tectonic; set TECTONIC_BIN for a custom binary.' >&2
  exit 127
fi
"${PYTHON_BIN:-python3}" scripts/embed_cjk_map.py main.pdf
mkdir -p ../../output/pdf
cp main.pdf ../../output/pdf/rag-paper.pdf
