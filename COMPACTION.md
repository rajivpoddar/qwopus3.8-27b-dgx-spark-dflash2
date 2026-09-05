# Compaction-only thinking override

Deployed image: `qwopus-compaction:v1` (2026-09-05), image ID
`sha256:dedc2d97b119189879fc4dbcd3618b047be0eb3a011adc81530b886a2fb7bffc`.
Container: `qwopus-pango-dflash-compaction`. Preserved rollback:
`qwopus-pango-dflash`. The launch arguments, environment and bind mounts were
verified unchanged; only the image changed.

Authenticated inference proof: dedicated compaction system prompt with explicit
client thinking enabled returned 0 thinking characters, all three synthetic
handoff facts, and `end_turn` in 8.611 seconds. Ordinary coding system prompt
with thinking enabled returned 312 thinking characters and `end_turn` in 2.863
seconds. These are short smoke probes, not a long-history compaction benchmark.
The policy log marker was emitted for the compaction probe. A naturally occurring
Claude compaction remains necessary to establish client-specific coverage.

The installed Claude Code 2.1.228 compaction call uses the dedicated system
prompt `You are a helpful AI assistant tasked with summarizing conversations.`
The adapter matches only that complete system string or a single equivalent
text block (cache-control metadata is allowed). User/history text never triggers
the policy. Unknown or changed system prompts keep the existing behavior.

After normal thinking/effort conversion, the policy invokes SGLang's explicit
reasoning-off path, overriding the server's thinking-on default and an enabled
client request. Normal coding requests retain their current policy. Output
budgets, messages, tools, sampling and cache handling are not changed. This does
not impose a summary length cap or remove analysis explicitly requested as text
by the compaction prompt. It is not a guaranteed cure for all compaction latency.

Build on the existing Spark, without loading another model:

```sh
docker tag sha256:db815495d86fa23ffa3c898ca48d3dcb5e2a09240a092fd99e4601bd53274bfa qwopus-compaction-base:db815495d86f
docker build --pull=false --network=none -f image/Dockerfile.compaction -t qwopus-compaction:v1 image
python3 -m unittest discover -s image/test -p test_compaction_policy.py
docker run --rm --network=none -v "$PWD/image/test/test_compaction_adapter.py:/test.py:ro" --entrypoint python qwopus-compaction:v1 /test.py
```

The build checks the exact deployed adapter SHA before inserting the override.
The adapter test exercises real Anthropic request conversion with a lightweight
reasoning backend; it does not test GPU generation or summary quality.

Activation requires a server maintenance window: pause requests without clearing
sessions, fence MoP, preserve the current container for rollback, and clone its
configuration with only the candidate image changed. Do not use the target-only
launcher or load a second model concurrently. Verify an authenticated compaction
probe emits no reasoning and preserves summary facts, and a normal thinking-on
probe still reasons. Require `compaction_policy: thinking disabled` in the log
for a real client compaction before claiming end-to-end coverage. Resume paused
requests sequentially, then restore MoP. Roll back to the preserved container
if validation fails. No slot restart or PM re-handoff is required.
