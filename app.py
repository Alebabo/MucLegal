import os
from pathlib import Path

from muclegal.live import LiveMonitorWorkflow
from muclegal.ui import create_app


ROOT = Path(__file__).resolve().parent
STORE = (ROOT / ".muclegal-ui").resolve()
WORKFLOW = LiveMonitorWorkflow(STORE, ROOT / "fixtures" / "tenor.json")
app = create_app(
    WORKFLOW.latest_case_path,
    STORE / "reviews.sqlite3",
    workflow=WORKFLOW,
    anthropic_ready=bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
    asset_directory=ROOT / "assets",
)

