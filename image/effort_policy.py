"""Qwopus effort -> strict grammar budget. Activated only in the effort image."""
import os
from sglang.srt.entrypoints.anthropic.compaction_policy import is_compaction

BUDGETS = {'low': 1024, 'medium': 4096, 'high': 8192, 'xhigh': 16384, 'max': 32768}


def apply_effort_policy(request, chat, serving):
    if os.environ.get('QWOPUS_EFFORT_BUDGETS') != '1':
        return
    args = serving.tokenizer_manager.server_args
    if not args.enable_strict_thinking or args.grammar_backend != 'xgrammar':
        raise ValueError('Qwopus effort budgets require --enable-strict-thinking --grammar-backend xgrammar')
    if int(os.environ.get('SGLANG_MAX_THINK_TOKENS', '-1')) < 0:
        raise ValueError('Qwopus effort budgets require nonnegative SGLANG_MAX_THINK_TOKENS')
    thinking = request.thinking
    effort = getattr(request.output_config, 'effort', None)
    if is_compaction(request.system) or (thinking and thinking.type == 'disabled') or effort == 'none':
        serving.apply_reasoning_enabled(chat, False)
        chat.custom_params = {**(chat.custom_params or {}), 'thinking_budget': 0}
        return
    if effort is not None and effort not in BUDGETS:
        raise ValueError('Unsupported Qwopus effort level')
    budget = BUDGETS.get(effort, BUDGETS['low'])
    explicit = getattr(thinking, 'budget_tokens', None)
    if explicit is not None:
        budget = min(budget, explicit) if effort else explicit
    # Preserve the caller's total limit. Reserve up to 1024 tokens for the answer;
    # short requests run without thinking rather than exhausting their total limit.
    budget = max(0, min(budget, request.max_tokens - 1024))
    serving.apply_reasoning_enabled(chat, budget > 0)
    chat.custom_params = {**(chat.custom_params or {}), 'thinking_budget': budget}
