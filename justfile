check:
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
