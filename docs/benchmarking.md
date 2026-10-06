# Benchmark protocol (planned)

Compare vanilla Codex, provenance-verified old toolkit, native policy, and Router v2 on identical pinned snapshots/model/settings. Cover bugfix, feature, tests, multi-file refactoring, architecture, dependency update, CI repair and large exploration across Rust/Go/Python/IaC.

Independent correctness tests, requirement coverage, regressions and security gates come first. Only quality-equivalent runs compare tokens, cached/fresh input, output/reasoning where available, tool calls, retries, wall time and cold/warm index/bootstrap overhead. Include failures and repeated randomized-order runs. Missing counters are unknown, not zero.

No private prompts, .env, source or credentials in telemetry. Local aggregate counters only by default. No performance benefit is claimed before measurements. Baseline comparison is blocked on verified legacy artifacts.
