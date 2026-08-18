from pathlib import Path

from muclegal.ui import create_app


STORE = Path(".muclegal-demo").resolve()
app = create_app(STORE / "latest-case.json", STORE / "reviews.sqlite3")

