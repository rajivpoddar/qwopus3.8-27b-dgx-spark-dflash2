"""Run inside the candidate image; exercises the actual Anthropic conversion."""
from types import SimpleNamespace as NS
from sglang.srt.entrypoints.anthropic.serving import AnthropicServing
from sglang.srt.entrypoints.anthropic.protocol import AnthropicMessagesRequest
from sglang.srt.entrypoints.anthropic.compaction_policy import COMPACTION_SYSTEM


class Backend:
    def apply_reasoning_enabled(self, request, enabled):
        request.chat_template_kwargs = {**(request.chat_template_kwargs or {}), 'enable_thinking': enabled}


adapter = AnthropicServing.__new__(AnthropicServing)
adapter.openai_serving_chat = Backend()
adapter._merge_inline_system = False
for system, expected in [(COMPACTION_SYSTEM, False), ('You are a coding assistant.', True)]:
    request = AnthropicMessagesRequest(model='qwen3.8-27b', max_tokens=4096,
        system=system, messages=[{'role':'user','content':'Continue the task.'}],
        thinking={'type':'enabled','budget_tokens':1024})
    result = adapter._convert_to_chat_completion_request(request)
    assert result.chat_template_kwargs['enable_thinking'] is expected
    assert result.max_tokens == 4096
print('PASS: real adapter overrides compaction only; output budget preserved')
