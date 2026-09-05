"""Narrow Claude Code compaction policy; never inspect conversation content."""

COMPACTION_SYSTEM = "You are a helpful AI assistant tasked with summarizing conversations."


def is_compaction(system):
    if isinstance(system, str):
        return system.strip() == COMPACTION_SYSTEM
    if not isinstance(system, list) or len(system) != 1:
        return False
    block = system[0]
    if isinstance(block, dict):
        kind, text = block.get("type"), block.get("text")
    else:
        kind, text = getattr(block, "type", None), getattr(block, "text", None)
    return kind == "text" and isinstance(text, str) and text.strip() == COMPACTION_SYSTEM


def apply_compaction_policy(anthropic_request, chat_request, serving):
    if not is_compaction(anthropic_request.system):
        return False
    serving.apply_reasoning_enabled(chat_request, False)
    return True
