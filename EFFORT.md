# Enforced effort candidate (not deployed)

The effort image maps Anthropic `output_config.effort` into SGLang's existing
`custom_params.thinking_budget` strict-reasoning grammar. This is not a prompt
hint and does not use the total output limit as the reasoning limit.

| Effort | Maximum reasoning tokens |
|---|---:|
| low / omitted | 1024 |
| medium | 4096 |
| high | 8192 |
| xhigh | 16384 |
| max | 32768 |

An explicit client thinking budget is honored; when effort is also specified,
the smaller budget wins. Up to 1024 tokens of the existing total output limit
are reserved for the answer: requests whose total limit is <=1024 run with
thinking off. This is headroom, not a guarantee that an answer/tool call fits.
Explicit thinking-disabled and the exact compaction-system match remain off.
The mapping uses the original effort field before the adapter collapses xhigh
to max. These are local operational defaults, not Qwopus-trained effort levels.

## Required activation settings

Build `image/Dockerfile.effort` on the compaction image. Replace only the image
plus these required settings during a separately authorized server restart:

```
--enable-strict-thinking --grammar-backend xgrammar
QWOPUS_EFFORT_BUDGETS=1
SGLANG_MAX_THINK_TOKENS=1024
```

The two environment variables are image defaults. When cloning a Docker
container's Config, explicitly update its Env too: copying the old Env can
override image defaults. The policy refuses requests with missing strict
thinking/xgrammar support rather than silently ignoring budgets. The global
limit enables the grammar's token-filter path; request budgets then override it.

The existing runtime applies the reasoning grammar's mask to DFlash target
verification. At the budget, the grammar permits only the thinking-end token,
then transitions to ordinary answer generation. It supports speculative state
rollback. No arbitrary custom-logit-processor execution is enabled.

## Validation and remaining proof

`image/test/test_effort_runtime.py` runs CPU-only in the candidate image. It
exercises actual Anthropic conversion, actual GrammarManager budget assignment,
and actual ReasonerGrammarObject token transitions for all five levels, plus
disabled/compaction paths and answer headroom. It uses a lightweight backend
for setting the chat-template toggle and observing vocabulary masks.

This proves policy/grammar behavior, not end-to-end GPU generation. Before live
adoption, verify emitted reasoning lengths and complete valid tool calls at low,
medium and high, with DFlash enabled, including a request with prior thinking
history. Check actual Claude requests carry the effort field. Existing default
compaction matching remains narrow and is not validated for every Claude mode.
Do not advertise effective slot levels until that live-client proof passes.

The upstream adapter may still print its generic "budget not enforced" warning
before this overlay assigns the strict budget; it describes the unpatched path.
No live server or slot settings are changed by building or testing this image.
