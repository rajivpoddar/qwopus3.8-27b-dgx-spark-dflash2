# Qwopus on the patched Pango runtime (experimental)

This guide includes the original **target-only baseline** and the subsequently
deployed **DFlash profile** (see the DFlash trial section below).
It reuses our fairness/Anthropic-heartbeat image described in
[STREAM_FIX.md](STREAM_FIX.md). It does not start a second model alongside Pango.
No model files are downloaded by this profile.

## Deliberate differences

- Target: `sojufx/Qwopus3.8-27B-Flash-NVFP4`, pinned to an explicit cached SHA.
- In the baseline, speculation is **off**. Do not reuse the base Qwen DFlash2 draft without testing
  compatibility, acceptance and output correctness against this fine-tune.
- Thinking **on** by default for this Qwopus profile (`enable_thinking=true`);
  `preserve_thinking` remains false. Generic Pango defaults remain unchanged.
- Use Qwopus's own JSON-tool template and `--tool-call-parser qwen`, not Pango's
  XML-parameter `qwen3_coder` parser/template. Qwopus's current template already
  keeps inline system messages in sequence. Test this through Anthropic serving;
  a source-text check alone does not prove adapter detection or cache reuse.
- Keep BF16 KV/SSM, memory fraction .80, context 262144, four running requests,
  prefill chunk 4096 and consecutive-prefill limit 1 for the initial comparison.
  Capacity must be remeasured after loading; the checkpoint allocation differs.
- Use Mamba/full-KV memory ratio **0.9**, not the speculative profile's 11.93.
  The initial target-only load with 11.93 allocated 61.8 GB of Mamba state but
  only 85,906 KV tokens, insufficient for the preserved long sessions.
  The corrected load allocated 579,916 KV tokens and 434 Mamba cache entries
  with 21.82 GB available after memory pools (2026-09-05, before kernel warmup).
- Keep port 30000, credentials and the client-facing alias `qwen3.8-27b` for
  existing clients. The underlying weights are Qwopus; this alias is intentional.

Source: [Qwopus model card](https://huggingface.co/sojufx/Qwopus3.8-27B-Flash-NVFP4).
Its NEXTN recipe is a later experiment: same target/draft checkpoint,
`modelopt_mixed` draft quantization, steps 2, top-k 1, draft tokens 3. Do not
enable NEXTN and DFLASH together, or assume those flags work in this pinned image.

## Prepare without touching production

The local default image ID is the deployed heartbeat/fairness image. On another
host, build `image/Dockerfile.stream-fix` on the fairness image following
[STREAM_FIX.md](STREAM_FIX.md), and set IMAGE to that verified image. An arbitrary
upstream Pango image does not contain the heartbeat or fairness changes.

Identify the complete **already-cached** Qwopus snapshot and existing mounts/key
path. If missing, stop; obtaining weights is a separate authorized action.

During an approved maintenance window, pause active requests in their existing
sessions, stop the current Pango container, and retain it unchanged for rollback.
Only then run on Spark:

```bash
REVISION=<full-cached-Qwopus-commit-sha> \
HF_CACHE=<existing-cache-root> \
SGLANG_CACHE=<existing-pango-tactic-cache> \
SPARK_API_KEY_FILE=<existing-api-key-file> \
bash ./serve-qwopus.sh
```

The script refuses to replace an existing `qwopus-pango` container. It does not
stop Pango, alter slot sessions, change MoP, or perform a cutover itself. Do not
run it on a different port to bypass the single-model memory constraint.

## Acceptance before slots resume

For this host's standalone cached directory (rather than an HF hub snapshot),
`activate-qwopus.py --activate` clones the exact preserved `qwen38-pango` Docker
configuration, mounts `/home/user/models/qwopus-nvfp4-e1fad175` read-only and
changes only the target, template/parser/thinking/speculation and cache ratio.
It checks the pinned revision and creates the stopped candidate before stopping
the source. Run only with clients paused and MoP fenced. It does not manage
slots or prove readiness; the operator must roll back on readiness failure.

The launcher's model listing/tokenize checks are startup diagnostics, **not full
inference readiness**. Require all of these before resuming paused requests:

1. Container running without unexpected restarts/OOM; authenticated Anthropic
   `/v1/messages` completes with the stable alias and thinking on. Verify the
   client's request does not override the server default to disable thinking.
2. A long JSON tool argument parses correctly and ends in `tool_use`/`message_stop`;
   heartbeat frames continue during buffered output. Do not execute test tools.
3. A changed inline reminder in an appended follow-up preserves earlier cache
   reuse and roles; cancellation drains its request. Compare one-stream then
   representative concurrent work for throughput, latency, queue and memory.

Resume existing sessions only after these pass. This server-only trial does not
require fresh Claude sessions; exhausted client retries may need a new continue
turn. Cache is cold after the model restart, so the first long request is slower.
Resume active slots individually and wait for each cold prefill to reach output
before admitting the next. Existing clients launched with
`MAX_THINKING_TOKENS=0` may omit the thinking field rather than explicitly send
`thinking.type=disabled`. Verify actual output/request behavior; the environment
variable alone does not prove that the server's thinking default is overridden.

If acceptance fails, stop the candidate, restart the preserved Pango container,
prove authenticated inference readiness, then resume existing sessions. A stopped
`unless-stopped` rollback container stays stopped across reboot; do not leave both
models running. No automatic rollback or live-service changes are performed here.

## Host trial receipt — 2026-09-05

- Qwopus revision `e1fad175b1f069b9e19a0293c561cefb516df7e4` loaded from
  the pre-existing standalone cache; no downloads. `qwopus-pango` replaces the
  preserved, stopped `qwen38-pango` on port 30000 using the same client alias/key.
- Anthropic long-tool probe: 2,070-character valid JSON argument, 143 thinking
  characters, 52.98 seconds. Changed inline-system follow-up: 4.18 seconds,
  7,296 cached tokens and 627 new tokens. Both ended with `tool_use` and
  `message_stop`. Maximum SSE gap was 5.95 seconds; no heartbeat was needed.
- Explicit cancellation after output began drained running/queued requests to
  zero. The deployed image retains the existing heartbeat/fairness patches.
- All original Claude sessions retained. S4, S5, S6 resumed sequentially;
  first cold contexts were approximately 201K, 207K, and 180K tokens. S5 and S6
  executed tools; S4 generated a long first response. No client/API error was
  observed during these resumes, but latency was poor, not a performance PASS.
- About 13 tok/s on the short single-stream test; 7.7 tok/s single-stream at
  201K context; roughly 10–15 tok/s aggregate during long-context decoding.
  A queued request appeared as the long contexts competed for the 580K shared
  cache. These are live workload observations, not controlled benchmarks.
- MoP healthy on release `d0299ced6a061c3cb82597d7a2054c98f5f18d4a`, Node
  22.13.1/ABI 127. It restarted at 08:31:18 UTC before the operator's restore;
  the maintenance fence did not persist for the entire staggered-resume phase.
  All six pane/shell identities, HEADs, dirty sets and assignment epochs matched
  the paused ledger afterward; the active Claude processes were unchanged.
- Rollback remains `docker stop -t 30 qwopus-pango` then
  `docker start qwen38-pango`, with requests paused and authenticated readiness
  checked before resuming. Do not run both models concurrently.

## DFlash trial — 2026-09-05

`activate-qwopus-dflash.py` performs a read-only preflight by default. During
an authorized maintenance window, `--activate` clones `qwopus-pango` and adds
the exact six speculative flags from the preserved `qwen38-pango` configuration.
The target is `qwopus-pango-dflash`; target-only rollback is `docker stop -t 30
qwopus-pango-dflash` then `docker start qwopus-pango`. No downloads, slot exits,
or fresh launches are performed by this script. Operator readiness proof and
staggered session resumption are still required.

- Cached draft: `maurienne-ai/Qwen3.8-27B-DFlash2-NVFP4-RTNcal`, revision
  `bd7a934213c47a9e7ef69eef36bb3325f47fd1f1`, `modelopt_fp4`, FlashInfer draft
  attention, 16 draft tokens. No NEXTN flags.
- Target-only settings otherwise unchanged, including Mamba/full-KV ratio 0.9.
  This load allocated 652,081 KV tokens, 96 Mamba entries, and left 22.41 GB
  available after target/draft pools.
- Same long-tool prompt: 12.051 seconds versus target-only 52.978 seconds;
  2,150-character valid argument versus 2,070; thinking 206 versus 143 characters.
  Temperature 0.6 means outputs differ: this is a smoke comparison, not a
  deterministic throughput benchmark. Observed acceptance was 11.03 tokens/pass.
- Cached follow-up: 1.729 seconds versus 4.182, with 7,296 reused tokens.
  Both tool turns completed with valid JSON and `message_stop`; cancellation
  drained the request queue. This does not establish losslessness across all
  workloads or predict long-context fleet throughput.
- S4 live canary at approximately 201K prompt tokens: sustained roughly
  20–27 tok/s while decoding alone, versus about 7.7 tok/s in the earlier
  target-only observation; acceptance typically 3–4 tokens/pass. Prompt and
  output were not byte-identical, so treat this as operational evidence, not
  a controlled speedup claim. Cold prefill remained several minutes.
- Cutover completed: PM acknowledged the maintenance hold, MoP stayed unloaded
  during the swap and staggered prefills, then was restored healthy on the same
  release/Node runtime. S4–S6 resumed without session restarts; S6 executed tools
  and reused a 183K-token prefix. All six pane/disk/epoch tuples matched the
  paused ledger. Final sampled workload had three running requests, zero queued,
  roughly 20 tok/s aggregate and 94% KV usage; mixed workload samples are not
  decode-only benchmarks. Target-only Qwopus remains intact for rollback.
