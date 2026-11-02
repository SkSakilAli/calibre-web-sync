"""Start command for the alwaysdata site:
   /home/YOUR_ACCOUNT/www/library/env/bin/python /home/YOUR_ACCOUNT/www/library/launch.py
"""
import os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
(DATA / "config").mkdir(parents=True, exist_ok=True)
(DATA / "library").mkdir(parents=True, exist_ok=True)

os.environ["CALIBRE_DBPATH"] = str(DATA / "config")   # app.db lives in the synced folder
if os.environ.get("PORT"):
    os.environ["CALIBRE_PORT"] = os.environ["PORT"]   # alwaysdata assigns the port
if os.environ.get("IP"):
    sys.argv += ["-i", os.environ["IP"]]              # and the address to listen on

sys.path.insert(0, str(HERE))
import sync_boot                  # noqa: E402  pull from the dataset, start the watcher
from cps.main import main         # noqa: E402  Calibre-Web entry point

main()
