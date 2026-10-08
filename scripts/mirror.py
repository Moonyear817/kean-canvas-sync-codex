#!/usr/bin/env python3
"""Copy every semester folder (大X秋季 …) under root into config "mirror_dir"
(e.g. a OneDrive folder) so the cloud copy stays current.

One-way and additive: new and changed local files are copied over; nothing
in the mirror is ever deleted, so a file removed locally stays in the cloud.
Does nothing when mirror_dir is empty or missing.
"""
import os, subprocess, sys
import config

cfg = config.load()
mirror = os.path.expanduser(cfg.get("mirror_dir") or "")
if not mirror:
    print("mirror_dir not set — skipped")
    sys.exit(0)

os.makedirs(mirror, exist_ok=True)
root = cfg["root"]
for term in sorted(os.listdir(root)):
    src = os.path.join(root, term)
    if os.path.isdir(src) and term.endswith("季"):
        subprocess.run(["rsync", "-a", "--exclude=.DS_Store", "--exclude=~$*",
                        "--exclude=*.part", "--exclude=*.crdownload", src, mirror + "/"], check=True)
        print(f"mirrored {term} -> {mirror}/{term}")
