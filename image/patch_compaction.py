"""Build-time patch against the exact deployed heartbeat adapter."""
import hashlib
from pathlib import Path

path = Path('/sgl-workspace/sglang/python/sglang/srt/entrypoints/anthropic/serving.py')
source = path.read_text()
assert hashlib.sha256(source.encode()).hexdigest() == '141fca39d6e05e34327e51c002718e77c23aa7d277762c0df4dfe79326a117a7', 'Unexpected adapter; review patch against new source'
anchor = '        # ``betas`` is the Anthropic SDK\'s opt-in feature list'
assert source.count(anchor) == 1
source = source.replace(anchor, '''        # Exact Claude Code compaction system prompt only. Ordinary turns retain
        # client/default reasoning policy. Do not log conversation contents.
        from sglang.srt.entrypoints.anthropic.compaction_policy import apply_compaction_policy
        if apply_compaction_policy(anthropic_request, chat_request, self.openai_serving_chat):
            logger.info("compaction_policy: thinking disabled")

''' + anchor)
compile(source, str(path), 'exec')
path.write_text(source)
