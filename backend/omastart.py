#!/usr/bin/env python3
"""One request per process; stdout is exclusively a bounded JSON response."""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True  # Installed plugin files are watched for hot reload.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.common import Error
from backend.engine import Engine


def main():
    try:
        if len(sys.argv) > 2 or len(sys.argv) == 2 and len(sys.argv[1]) > 32_768:
            raise Error("Invalid request size.")
        request = json.loads(sys.argv[1]) if len(sys.argv) == 2 else {"action": "scan"}
        result = Engine().request(request)
    except (Error, OSError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
    except Exception:
        # Keep traceback out of the UI but available in captured stderr/logs.
        import traceback
        traceback.print_exc(file=sys.stderr)
        result = {"ok": False, "error": "Unexpected backend error. Refresh and inspect the shell log."}
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
