#!/usr/bin/env python3
"""Read-only fingerprints for before/after live acceptance (no file contents)."""
import hashlib
import json
import os
from pathlib import Path

home = Path.home()
config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
roots = [config / "autostart", config / "systemd/user", config / "hypr/autostart.lua",
         config / "omarchy/plugins/smartalb.autostart", Path("/etc/systemd/user"), Path("/etc/xdg/autostart")]
result = {}
for root in roots:
    paths = sorted(root.rglob("*")) if root.is_dir() else [root]
    for path in paths:
        if ".git" in path.parts:
            continue
        if path.is_symlink():
            result[str(path)] = {"link": os.readlink(path)}
        elif path.is_file():
            result[str(path)] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "mode": path.stat().st_mode & 0o777}
print(json.dumps(result, sort_keys=True, indent=2))
