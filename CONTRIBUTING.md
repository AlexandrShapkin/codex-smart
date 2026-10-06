# Contributing

Use focused issues and branches with small Conventional Commits. Keep core logic pure where practical. Add regression tests before fixes; use fake executables and isolated directories for integrations. Do not require host MCP installations in tests.

Run `just check` before a commit and inspect `git diff`. CI runs the same commands. Do not push, merge, release or publish packages without authorization. Update roadmap/issues and changelog at logical release boundaries. Report limitations honestly.

PRs should describe Problem, Approach, Changes, Testing, Risks and Follow-ups. See [development](docs/development.md).
