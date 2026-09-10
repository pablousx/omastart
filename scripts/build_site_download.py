#!/usr/bin/env python3
"""Refresh the self-contained website's source download and plugin assets.

Only the explicit source directories below are packaged. Local state, Git
metadata, website files, and installed runtime snapshots never enter the ZIP.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

root = Path(__file__).resolve().parent.parent
assets = root / "docs" / "assets"
version = json.loads((root / "manifest.json").read_text())["version"]
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
    raise SystemExit("Expected a numeric major.minor.patch manifest version")
archive = assets / f"omastart-{version}.zip"
files = [root / name for name in ("README.md", "VERIFICATION.md", "LICENSE", "manifest.json", "preview.png")]
files += list(root.glob("*.qml")) + list(root.glob("*.js"))
for directory in ("backend", "scripts", "tests"):
    files += list((root / directory).rglob("*.py"))
    files += list((root / directory).rglob("*.qml"))
assets.mkdir(parents=True, exist_ok=True)
with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as output:
    for path in sorted(set(files)):
        if path.is_symlink() or not path.is_file():
            raise SystemExit(f"Expected a regular source file: {path}")
        info = ZipInfo(f"omastart-{version}/{path.relative_to(root)}", date_time=(2026, 9, 10, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (0o100644 << 16)
        info.compress_type = ZIP_DEFLATED
        output.writestr(info, path.read_bytes(), compresslevel=9)
shutil.copyfile(root / "LICENSE", assets / "LICENSE.txt")
shutil.copyfile(root / "preview.png", assets / "panel.png")
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(assets / "SHA256SUMS.txt").write_text(f"{digest}  {archive.name}\n")
print(f"Built {archive.relative_to(root)}: {len(files)} files, {archive.stat().st_size:,} bytes\nSHA256 {digest}")
