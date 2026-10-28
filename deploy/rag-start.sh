#!/usr/bin/env bash
# Run on the GPU host; only this dedicated RAG container is managed here.
set -euo pipefail
workspace=${RAG_WORKSPACE:-/opt/accelerator-rag}
name=accelerator-rag
image=${RAG_RUNTIME_IMAGE:-accelerator-rag-runtime:20261026}
gpu=${RAG_GPU_DEVICE:-2}
# Credentials must be inherited or supplied from a mode-600 file outside the repo.
args=()
if [[ -n "${RAG_ENV_FILE:-}" ]]; then args+=(--env-file "$RAG_ENV_FILE"); fi
for key in ACCELERATOR_MODEL_BASE_URL ACCELERATOR_MODEL_NAME ACCELERATOR_MODEL_API_KEY; do
  if [[ -n "${!key:-}" ]]; then args+=(-e "$key"); fi
done
if docker inspect "$name" >/dev/null 2>&1; then
  mounted=$(docker inspect "$name" --format '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.Source}}{{end}}{{end}}')
  test "$mounted" = "$workspace"
  docker stop "$name" >/dev/null
  docker rm "$name" >/dev/null
fi
docker run -d --name "$name" --label accelerator-rag.service=standalone \
  --gpus "device=$gpu" --network host --ipc host --restart unless-stopped \
  -v "$workspace:/workspace:ro" -v "$workspace/tmp:/workspace/tmp" -w /workspace \
  -e PYTHONPATH=/workspace/src -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -e HF_HUB_DISABLE_PROGRESS_BARS=1 -e TOKENIZERS_PARALLELISM=false -e OMP_NUM_THREADS=6 \
  "${args[@]}" \
  --health-cmd 'curl -fsS http://127.0.0.1:8003/health >/dev/null' \
  --health-start-period=120s --health-interval=30s --health-timeout=5s --health-retries=3 \
  --entrypoint /usr/bin/python3 "$image" \
  -m accelerator_rag.rag --config config/rag-production.json --host 0.0.0.0 --port 8003
