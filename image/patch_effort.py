"""Apply the effort policy after compaction/effort conversion."""
from pathlib import Path

p = Path('/sgl-workspace/sglang/python/sglang/srt/entrypoints/anthropic/serving.py')
s = p.read_text()
anchor = '        # ``betas`` is the Anthropic SDK\'s opt-in feature list'
assert s.count(anchor) == 1 and 'apply_compaction_policy' in s
assert 'apply_effort_policy' not in s
s = s.replace(anchor, '''        from sglang.srt.entrypoints.anthropic.effort_policy import apply_effort_policy
        apply_effort_policy(anthropic_request, chat_request, self.openai_serving_chat)

''' + anchor)
p.write_text(s)
compile(s, str(p), 'exec')
