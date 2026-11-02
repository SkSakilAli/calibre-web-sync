"""Imported by launch.py before Calibre-Web starts.

Pulls the library from the Hugging Face dataset, seeds the dataset on the very
first run, then starts a background thread that pushes changes.
Everything is logged to sync.log next to this file. Errors never stop the app.
"""
import os, sys, subprocess, threading, traceback, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = os.path.join(HERE, "sync.log")


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def ensure_dep():
    try:
        import huggingface_hub  # noqa: F401
        return
    except ImportError:
        pass
    log("installing huggingface_hub (first run only)")
    cmd = [sys.executable, "-m", "pip", "install", "huggingface_hub"]
    if sys.prefix == getattr(sys, "base_prefix", sys.prefix):  # not inside a virtualenv
        cmd.insert(4, "--user")
    r = subprocess.run(cmd, capture_output=True, text=True)
    log((r.stdout + r.stderr)[-600:])
    import site, importlib
    sys.path.append(site.getusersitepackages())
    importlib.invalidate_caches()


def start():
    try:
        ensure_dep()
        import hfsync
        log(f"enter this as the Calibre database location: {hfsync.BASE / 'library'}")
        hfsync.pull()
        log("pull ok")
        remote = set(hfsync.api.list_repo_files(hfsync.REPO, repo_type="dataset"))
        if ("library/metadata.db" not in remote
                and (hfsync.BASE / "library" / "metadata.db").exists()):
            hfsync.push()
            log("seeded dataset")
        threading.Thread(target=hfsync.watch, daemon=True).start()
        log("watcher started")
    except BaseException:
        log(traceback.format_exc())


start()
