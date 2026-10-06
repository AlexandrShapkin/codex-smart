"""Run optional coverage only when LLVM tools already exist; never install them."""
import os
import subprocess
from pathlib import Path

explicit = [os.environ.get("LLVM_COV"), os.environ.get("LLVM_PROFDATA")]
if any(explicit):
    if not all(explicit) or not all(Path(p).is_absolute() and os.access(p, os.X_OK) for p in explicit):
        raise SystemExit("Coverage requires both existing absolute LLVM_COV and LLVM_PROFDATA executables")
else:
    root = subprocess.run(["rustc", "--print", "sysroot"], check=True, capture_output=True, text=True, timeout=15).stdout.strip()
    details = subprocess.run(["rustc", "-vV"], check=True, capture_output=True, text=True, timeout=15).stdout
    host = next(line.removeprefix("host: ") for line in details.splitlines() if line.startswith("host: "))
    tools = Path(root) / "lib/rustlib" / host / "bin"
    if not all((tools / name).is_file() for name in ("llvm-cov", "llvm-profdata")):
        raise SystemExit("Coverage unavailable: LLVM tools absent. Install llvm-tools-preview explicitly or provide compatible LLVM_COV/LLVM_PROFDATA. No installation attempted.")
raise SystemExit(subprocess.call(["cargo", "llvm-cov", "--workspace", "--all-features", "--locked"]))
