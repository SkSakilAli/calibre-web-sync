#!/usr/bin/env python3
"""Hugging Face dataset = source of truth; local ./data folder = cache.

Usage: python hfsync.py pull | push | watch

Environment variables:
  HF_REPO        dataset id, e.g. "yourname/calibre-library"   (required)
  HF_TOKEN       fine-grained token with write access to that dataset (required)
  CALIBRE_BASE   optional override of the local folder (default: ./data next to this file)
  SYNC_INTERVAL  seconds between change checks (default 120)

Dataset layout:
  library/   Calibre library (metadata.db + book folders)
  config/    Calibre-Web settings (app.db)
"""
import os, sys, time, shutil, sqlite3, hashlib, tempfile
from pathlib import Path
from huggingface_hub import (HfApi, snapshot_download,
                             CommitOperationAdd, CommitOperationDelete)

REPO = os.environ["HF_REPO"]
TOKEN = os.environ["HF_TOKEN"]
BASE = Path(os.environ.get("CALIBRE_BASE", Path(__file__).resolve().parent / "data"))
INTERVAL = int(os.environ.get("SYNC_INTERVAL", "120"))
STATE = BASE / ".sync_state"
api = HfApi(token=TOKEN)


def skip(p: Path) -> bool:
    n = p.name
    return (".cache" in p.parts
            or n.endswith(("-journal", "-wal", "-shm", ".tmp"))
            or n == ".sync_state")


def files():
    return [p for p in sorted(BASE.rglob("*")) if p.is_file() and not skip(p)]


def fingerprint() -> str:
    h = hashlib.sha1()
    for p in files():
        st = p.stat()
        h.update(f"{p.relative_to(BASE)}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()


def pull():
    BASE.mkdir(parents=True, exist_ok=True)
    api.create_repo(REPO, repo_type="dataset", private=True, exist_ok=True)
    snapshot_download(repo_id=REPO, repo_type="dataset", local_dir=BASE, token=TOKEN)
    STATE.write_text(fingerprint())
    print("pulled")


def snap_db(src: Path, dst: Path):
    """Consistent copy of a live SQLite database."""
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(dst)
    s.backup(d)
    d.close()
    s.close()


def push():
    if not (BASE / "library" / "metadata.db").exists():
        sys.exit("refusing to push: library/metadata.db is missing locally")
    tmp = Path(tempfile.mkdtemp())
    try:
        ops, local = [], set()
        for p in files():
            rel = p.relative_to(BASE).as_posix()
            local.add(rel)
            src = p
            if p.suffix == ".db":
                src = tmp / rel.replace("/", "__")
                snap_db(p, src)
            ops.append(CommitOperationAdd(path_in_repo=rel, path_or_fileobj=str(src)))
        remote = set(api.list_repo_files(REPO, repo_type="dataset"))
        gone = remote - local - {".gitattributes", "README.md"}
        if len(gone) > 20 and not os.environ.get("FORCE"):
            sys.exit(f"refusing to delete {len(gone)} remote files (set FORCE=1 to allow)")
        ops += [CommitOperationDelete(path_in_repo=r) for r in gone]
        api.create_commit(repo_id=REPO, repo_type="dataset", operations=ops,
                          commit_message="sync")
        STATE.write_text(fingerprint())
        print("pushed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def watch():
    while True:
        time.sleep(INTERVAL)
        try:
            state = STATE.read_text() if STATE.exists() else ""
            if fingerprint() != state:
                push()
        except BaseException as e:   # sys.exit() inside push() must not kill the thread
            print("sync error:", e, file=sys.stderr)


if __name__ == "__main__":
    {"pull": pull, "push": push, "watch": watch}[sys.argv[1]]()
