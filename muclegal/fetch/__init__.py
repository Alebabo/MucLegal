from muclegal.fetch.http import FetchFailure, FetchPolicy, FetchResult, HttpFetcher
from muclegal.fetch.playwright import (
    DomInspectionCapture,
    ScreenshotCapture,
    ScreenshotCaptureError,
    capture_page_screenshot,
    inspect_expected_element,
)

__all__ = [
    "DomInspectionCapture",
    "FetchFailure",
    "FetchPolicy",
    "FetchResult",
    "HttpFetcher",
    "ScreenshotCapture",
    "ScreenshotCaptureError",
    "capture_page_screenshot",
    "inspect_expected_element",
]
