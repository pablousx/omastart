#!/usr/bin/python3
"""Bound the QML-to-backend process boundary and relay one JSON response."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Error, bounded_process, closed_environment


MAX_RESPONSE = 2_000_000


def main():
    try:
        if len(sys.argv) != 3 or len(sys.argv[2]) > 32_768:
            raise Error("Invalid backend request.")
        backend = Path(sys.argv[1])
        expected = Path(__file__).resolve().with_name("omastart.py")
        if backend.resolve() != expected:
            raise Error("Refusing an unexpected backend path.")
        result = bounded_process(
            ["/usr/bin/python3", "-I", "-B", str(expected), sys.argv[2]],
            timeout=20,
            env=closed_environment(),
            stdout_limit=MAX_RESPONSE,
            stderr_limit=64_000,
        )
        output = result.stdout
        if len(output.encode()) > MAX_RESPONSE:
            raise Error("Backend response exceeded the safety limit.")
        sys.stdout.write(output)
        if result.stderr:
            sys.stderr.write(result.stderr[:64_000])
        return result.returncode
    except Error as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": str(exc)}, separators=(",", ":")) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
