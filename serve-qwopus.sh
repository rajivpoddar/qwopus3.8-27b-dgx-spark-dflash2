#!/usr/bin/env bash
# Target-only Qwopus on the tested Pango heartbeat/fairness runtime.
# Run only during an approved server maintenance window; never stops Pango.
set -euo pipefail
RECIPE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export MODEL=sojufx/Qwopus3.8-27B-Flash-NVFP4
: "${REVISION:?Set REVISION to the full SHA of the already-cached Qwopus snapshot}"
[[ "$REVISION" =~ ^[0-9a-f]{40}$ ]] || { echo 'REVISION must be a full commit SHA' >&2; exit 2; }
: "${HF_CACHE:?Set HF_CACHE to the existing Hugging Face cache root containing hub/}"
: "${SGLANG_CACHE:?Set SGLANG_CACHE to the existing Pango tactic cache}"
: "${SPARK_API_KEY_FILE:?Set SPARK_API_KEY_FILE to the existing API key file}"
[ "${SPEC:-0}" = 0 ] || { echo 'Only SPEC=0 is validated by this profile; DFlash/NEXTN require separate testing.' >&2; exit 2; }
[ -z "${EXTRA_ARGS:-}" ] || { echo 'EXTRA_ARGS is not supported by this baseline profile.' >&2; exit 2; }
export SPEC=0 REPLACE_EXISTING=0 TOOL_PARSER=qwen
export ENABLE_THINKING=true
export IMAGE=${IMAGE:-sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa}
export NAME=${NAME:-qwopus-pango} PORT=${PORT:-30000}
if [ "$(docker container inspect --format '{{.State.Running}}' "${PANGO_CONTAINER:-qwen38-pango}" 2>/dev/null || true)" = true ]; then
  echo 'REFUSED: Pango is still running; this profile replaces it, not runs alongside it.' >&2
  exit 2
fi
export MEM_FRACTION=${MEM_FRACTION:-0.80} CHUNK=${CHUNK:-4096}
export KV_DTYPE=bfloat16 SSM_DTYPE=bfloat16
export CTX=${CTX:-262144} MAX_RUNNING=${MAX_RUNNING:-4}
export MAMBA_MEMORY_RATIO=0.9
export EXTRA_ARGS='--max-consecutive-prefill-batches 1'
snapshot="${HF_CACHE}/hub/models--sojufx--Qwopus3.8-27B-Flash-NVFP4/snapshots/${REVISION}"
# No downloads, and do not mistake one shard for a complete checkpoint.
python3 - "$snapshot" <<'PY'
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
for name in ('config.json', 'hf_quant_config.json', 'tokenizer.json', 'chat_template.jinja', 'model.safetensors.index.json'):
    if not (p / name).is_file():
        raise SystemExit('Missing cached file: ' + name)
index = json.loads((p / 'model.safetensors.index.json').read_text())
shards = set(index['weight_map'].values())
if not shards or any(not (p / name).is_file() or (p / name).stat().st_size == 0 for name in shards):
    raise SystemExit('Incomplete cached weight shards')
template = (p / 'chat_template.jinja').read_text()
if '(message.role == "system" and not loop.first)' not in template or '<tool_call>' not in template:
    raise SystemExit('Template changed: review inline-system preservation and JSON tool format before launch')
PY
export CHAT_TEMPLATE="/root/.cache/huggingface/hub/models--sojufx--Qwopus3.8-27B-Flash-NVFP4/snapshots/${REVISION}/chat_template.jinja"
docker image inspect "$IMAGE" >/dev/null
exec bash "$RECIPE_DIR/serve.sh"
