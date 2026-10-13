default:
    @just --list --unsorted

# Explicit repository state; never invoked by offline context/docs checks.
status:
    @python3 -B scripts/workflow.py repo-inspect

# Explicit network fetch + new worktree; source checkout may be dirty/diverged.
task-start branch destination sha:
    @python3 -B scripts/workflow.py task-start --branch {{quote(branch)}} --destination {{quote(destination)}} --expected-sha {{quote(sha)}}

source-verify sha:
    @python3 -B scripts/workflow.py source-verify --expected-sha {{quote(sha)}}

# Writes only a NEW directory; no installation, activation or remote transfer.
snapshot-export sha destination:
    @python3 -B scripts/workflow.py snapshot-export --expected-sha {{quote(sha)}} --destination {{quote(destination)}}

# Works on deployment directories without .git; digest must come from trusted export.
snapshot-verify snapshot sha receipt_sha256:
    @python3 -B scripts/workflow.py snapshot-verify --snapshot {{quote(snapshot)}} --expected-sha {{quote(sha)}} --receipt-sha256 {{quote(receipt_sha256)}}

# Offline bounded contract and source pointers; defaults to the active stage.
context stage="":
    @python3 -B scripts/workflow.py context {{quote(stage)}}

# Explicit live GitHub metadata; never called by context or docs-check.
issues:
    gh issue list --repo AlexandrShapkin/codex-smart --state all --limit 100 --json number,title,state,url

docs-check:
    python3 -B scripts/workflow.py check

docs-generate:
    python3 -B scripts/workflow.py generate

alias docs-sync := docs-generate
alias deny := security

check:
    python3 -B scripts/workflow.py check
    python3 -B -m unittest discover -s scripts -p 'test_*.py'
    cargo fmt --check
    cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
    cargo test --workspace --all-features --locked
    cargo build --workspace --all-features --locked

nextest:
    cargo nextest run --workspace --all-features --locked

coverage:
    python3 scripts/coverage.py

# Explicit network step, restricted to the public advisory database.
security-fetch:
    cargo deny --locked fetch db

# Assumes `just security-fetch` populated the advisory cache first.
security:
    python3 scripts/check_dependencies.py
    cargo deny --frozen check -D warnings
