# Enforced effort budgets

## Operator force-off experiment

`QWOPUS_FORCE_THINKING_OFF=1` overrides all Anthropic client thinking and effort
settings before the budget policy. It sets `enable_thinking=false` and the
strict grammar budget to zero without changing the total answer limit.
This override covers the slots' Anthropic endpoint, not arbitrary OpenAI clients.
Build `image/Dockerfile.thinking-off` and explicitly set the variable when
cloning container configuration. Deploy with paused requests and preserved slot
sessions; no clear or slot restart is required. Roll back to the preserved effort
container to restore effort behavior. This does not eliminate cold prefill cost.

Deployed 2026-09-05 as `qwopus-pango-dflash-thinking-off`, image
`sha256:dd967e4ffa4bf055589c5a8fda4a8823b2c9f33b89dc622087d35667babb1c65`.
Four CPU integration tests passed. Live authenticated curl explicitly requested
enabled thinking, a 32768-token budget and max effort: HTTP 200, zero thinking
characters, valid `record_result` tool call, 28 output tokens. No tool was
executed. Model discovery passed; startup had zero restarts and no OOM.
The preserved rollback container is `qwopus-pango-dflash-effort`.

## Deployment receipt — 2026-09-05

Deployed `qwopus-pango-dflash-effort`, image
`sha256:e11dc62385a2af8c0a242a5eb85490b91844d897605166b26c72e645b408f121`,
with strict thinking, xgrammar, and the two environment settings below.
`activate-effort.py` preserves the prior container for rollback. No model assets
or Claude sessions were replaced. Authenticated model discovery and Anthropic
inference passed; startup had zero restarts and no OOM.

Live DFlash probes for low, medium, and high each returned a valid synthetic
tool call. These used an explicit 1024-token budget, so they prove compatibility,
not saturation of the distinct default caps. A separate headroom-bound probe
with a 64-token effective reasoning budget emitted 63 retokenized thinking
tokens and completed a valid tool call. The exact compaction-system probe
returned zero thinking and a complete answer. No synthetic tool was executed.

The CPU integration test covers all five default budget mappings and the real
grammar transition at each cap. Full-cap GPU saturation and naturally occurring
Claude effort/compaction request matching remain follow-up validation; do not
infer them from the short synthetic probes.

Rollback: stop `qwopus-pango-dflash-effort`, start the preserved
`qwopus-pango-dflash-compaction`, and verify authenticated inference before
resuming requests. Do not run the two model servers concurrently.

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

This test proves policy/grammar behavior, not end-to-end GPU generation. The
deployment probes above additionally cover short GPU tool calls and a forced
budget boundary. Still validate a request with prior thinking history and check
actual Claude requests carry the effort field. Existing default
compaction matching remains narrow and is not validated for every Claude mode.
Do not advertise effective slot levels until that live-client proof passes.

The upstream adapter may still print its generic "budget not enforced" warning
before this overlay assigns the strict budget; it describes the unpatched path.
No live server or slot settings are changed by building or testing this image.
