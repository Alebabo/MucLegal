import os
from pathlib import Path

from muclegal.live import LiveMonitorWorkflow
from muclegal.fetch import FetchPolicy, HttpFetcher, inspect_expected_element
from muclegal.domain_monitor import CaseDomainMonitor
from muclegal.monitoring_cases import MonitoringCaseRepository
from muclegal.evidence.wayback import WaybackClient
from muclegal.llm.tenor import AnthropicTenorAnalyzer, DeterministicTenorAnalyzer
from muclegal.llm.clause_analysis import AnthropicClauseAnalyzer, DeterministicClauseAnalyzer
from muclegal.ui import create_app


ROOT = Path(__file__).resolve().parent
STORE = Path(
    os.environ.get("MUCLEGAL_STORE", str(ROOT / ".muclegal-ui"))
).resolve()
ANTHROPIC_READY = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
FETCHER = HttpFetcher(
    FetchPolicy(timeout_seconds=10, max_attempts=2, require_public_network=True)
)
WORKFLOW = LiveMonitorWorkflow(
    STORE,
    ROOT / "fixtures" / "tenor.json",
    fetcher=FETCHER,
    wayback_client=WaybackClient(
        access_key=os.environ.get("WAYBACK_ACCESS_KEY"),
        secret_key=os.environ.get("WAYBACK_SECRET_KEY"),
    ),
    screenshot_capturer=FETCHER.capture_screenshot,
    clause_analyzer_factory=(
        AnthropicClauseAnalyzer if ANTHROPIC_READY else DeterministicClauseAnalyzer
    ),
)
MONITORING_CASES = MonitoringCaseRepository(STORE / "reviews.sqlite3", STORE / "case-intake")
DOMAIN_MONITOR = CaseDomainMonitor(
    STORE / "domain-monitoring",
    fetcher=WORKFLOW.fetcher,
    dom_inspector=inspect_expected_element,
)
app = create_app(
    WORKFLOW.latest_case_path,
    STORE / "reviews.sqlite3",
    workflow=WORKFLOW,
    anthropic_ready=ANTHROPIC_READY,
    asset_directory=ROOT / "assets",
    tenor_analyzer_factory=(AnthropicTenorAnalyzer if ANTHROPIC_READY else DeterministicTenorAnalyzer),
    monitoring_cases=MONITORING_CASES,
    domain_monitor=DOMAIN_MONITOR,
    allowed_hosts=[
        "127.0.0.1",
        "localhost",
        "testserver",
    ],
)

