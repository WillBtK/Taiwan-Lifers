"""Provenance helpers.

Every row written to the `tlfx` schema carries four provenance columns
(`source_url`, `source_doc`, `retrieved_at`, `vintage`) and, where the
observation sits on either side of a definitional break, a `basis` flag.

Two distinct kinds of break exist and must not be conflated:

* `AccountingBasis` — IFRS 4 vs IFRS 17 / TW-ICS, from 1 January 2026.
  Applies to `firm_quarterly` and anything derived from it.
* `MeasurementBasis` — whether a CBC series is disclosed by the central
  bank or estimated by us (the swap book before 2020, the 2019-style PnL
  regression backfill). README section 9: never splice the two without a
  flag.

`SPLICED` marks a series deliberately joined across such a break; the
artifact renders those segments dashed with a `.chip`, never as a
continuous line.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import certifi
import requests

# User-Agent policy. No single string works everywhere, so it is per-host.
#
# Measured 2026-09-03 against fred.stlouisfed.org/graph/fredgraph.csv:
#   curl/8.5.0            200 in 0.7s
#   python-requests/2.32  200 in 0.4s
#   Wget/1.21             200 in 1.4s
#   TLFX-monitor/0.1      read timeout (>18s)
#   Chrome browser string read timeout (>18s)
# FRED's edge tarpits User-Agents it does not recognise, so a descriptive
# custom string is the one thing that fails there. Conversely ir.ctbcholding.com
# returns 403 to anything that is not a browser string.
#
# Default is the honest descriptive string; the overrides below are the two
# exceptions, each recorded with its measured reason.
USER_AGENT = "TLFX-monitor/0.1 (macro research; contact via repository)"

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
# The client library actually in use — accepted by FRED's edge, unlike a
# custom string. Not a disguise: this is what requests would send by default.
_LIBRARY_UA = "python-requests/2.32"

USER_AGENT_OVERRIDES: dict[str, str] = {
    # 403 to non-browser agents
    "ir.ctbcholding.com": _BROWSER_UA,
    "media-ctbc.todayir.com": _BROWSER_UA,
    "www.ir-cloud.com": _BROWSER_UA,
    "www.irpro.co": _BROWSER_UA,
    # tarpits unrecognised agents
    "fred.stlouisfed.org": _LIBRARY_UA,
    "api.stlouisfed.org": _LIBRARY_UA,
    "www.stlouisfed.org": _LIBRARY_UA,
}


def ua_for(url: str) -> str:
    """User-Agent to send to `url`'s host."""
    return USER_AGENT_OVERRIDES.get(urlparse(url).hostname or "", USER_AGENT)


# TLS trust. `*.tii.org.tw` serves its leaf certificate without the issuing
# intermediate (TWCA Secure SSL Certification Authority), so any client
# without that intermediate cached fails with "unable to get local issuer
# certificate" — browsers succeed only because they fetch it via AIA. The
# intermediate is checked into config/certs/; it chains to TWCA Global Root
# CA, which is in the system and certifi stores (`openssl verify` OK,
# 2026-09-03). Verification is never disabled; the missing link is supplied.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXTRA_INTERMEDIATES: dict[str, Path] = {
    "tii.org.tw": _REPO_ROOT / "config" / "certs" / "twca_secure_ssl_ca.pem",
}
_BUNDLE_CACHE: dict[str, str] = {}


def ca_bundle_for(url: str) -> str | bool:
    """Value for requests' `verify=` when fetching `url`.

    True (the default trust store) for every host except those listed in
    `_EXTRA_INTERMEDIATES`, which get a merged bundle: the default store plus
    the intermediate their server omits. Merged bundles are written once per
    process to a temp file.
    """
    host = urlparse(url).hostname or ""
    for suffix, pem in _EXTRA_INTERMEDIATES.items():
        if host == suffix or host.endswith("." + suffix):
            if suffix not in _BUNDLE_CACHE:
                base = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") or certifi.where()
                merged = Path(tempfile.gettempdir()) / f"tlfx-ca-{suffix}.pem"
                merged.write_bytes(Path(base).read_bytes() + b"\n" + pem.read_bytes())
                _BUNDLE_CACHE[suffix] = str(merged)
            return _BUNDLE_CACHE[suffix]
    return True


DEFAULT_TIMEOUT = 45
RETRY_BACKOFF = (2, 4, 8, 16)


class AccountingBasis(str, Enum):
    IFRS4 = "IFRS4"
    IFRS17 = "IFRS17"


class MeasurementBasis(str, Enum):
    DISCLOSED = "disclosed"
    ESTIMATED = "estimated"
    SPLICED = "spliced"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class Provenance:
    """Where one observation came from, and as of when.

    `vintage` is the *data* date the publisher stamped on the release
    (e.g. the reference month of an FSC press release), which is not the
    same as `retrieved_at`, the wall-clock time we fetched it. Revisions
    are handled by keeping both and never overwriting a prior vintage.
    """

    source_url: str
    source_doc: str
    retrieved_at: datetime
    vintage: date | None = None
    content_sha256: str | None = None
    http_status: int | None = None
    basis: str | None = None
    note: str | None = None

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["retrieved_at"] = self.retrieved_at.isoformat()
        row["vintage"] = self.vintage.isoformat() if self.vintage else None
        return row


@dataclass
class FetchResult:
    content: bytes
    provenance: Provenance
    final_url: str
    elapsed_s: float

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def fetch(
    url: str,
    *,
    source_doc: str,
    vintage: date | None = None,
    basis: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    headers: Mapping[str, str] | None = None,
    retries: tuple[int, ...] = RETRY_BACKOFF,
) -> FetchResult:
    """GET `url`, returning content plus a populated `Provenance`.

    Retries on transport errors and 5xx with exponential backoff. A 4xx is
    returned to the caller rather than retried — it is a source change, not
    a transient failure, and should surface in the run log.
    """
    hdrs = {"User-Agent": ua_for(url), "Accept": "*/*"}
    if headers:
        hdrs.update(headers)

    last_exc: Exception | None = None
    for attempt, delay in enumerate((0,) + tuple(retries)):
        if delay:
            time.sleep(delay)
        started = time.monotonic()
        try:
            resp = requests.get(url, headers=hdrs, timeout=timeout, verify=ca_bundle_for(url))
        except requests.RequestException as exc:  # transport failure
            last_exc = exc
            continue
        elapsed = time.monotonic() - started
        if resp.status_code >= 500 and attempt < len(retries):
            last_exc = requests.HTTPError(f"{resp.status_code} from {url}")
            continue
        return FetchResult(
            content=resp.content,
            final_url=resp.url,
            elapsed_s=elapsed,
            provenance=Provenance(
                source_url=url,
                source_doc=source_doc,
                retrieved_at=utc_now(),
                vintage=vintage,
                content_sha256=sha256_hex(resp.content),
                http_status=resp.status_code,
                basis=basis,
            ),
        )
    raise RuntimeError(f"fetch failed after {len(retries) + 1} attempts: {url}") from last_exc


@dataclass
class ReconciliationCheck:
    """A Stage-level reconciliation test. README section 3: > 3% fails the run."""

    name: str
    lhs: float
    rhs: float
    tolerance: float = 0.03
    unit: str = "ratio"

    @property
    def rel_error(self) -> float:
        denom = abs(self.rhs) if self.rhs else 1.0
        return abs(self.lhs - self.rhs) / denom

    @property
    def passed(self) -> bool:
        return self.rel_error <= self.tolerance

    def as_row(self) -> dict[str, Any]:
        return {
            "check_name": self.name,
            "lhs": self.lhs,
            "rhs": self.rhs,
            "tolerance": self.tolerance,
            "rel_error": round(self.rel_error, 6),
            "passed": self.passed,
            "unit": self.unit,
        }


@dataclass
class RunLog:
    """Accumulates per-run source status and check results for `tlfx.run_log`."""

    stage: str
    started_at: datetime = field(default_factory=utc_now)
    sources: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def record_source(self, prov: Provenance, *, ok: bool, note: str | None = None) -> None:
        row = prov.as_row()
        row.update({"ok": ok, "note": note})
        self.sources.append(row)

    def record_check(self, check: ReconciliationCheck) -> None:
        self.checks.append(check.as_row())

    @property
    def failed_checks(self) -> list[dict[str, Any]]:
        return [c for c in self.checks if not c["passed"]]

    def summary(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "started_at": self.started_at.isoformat(),
            "finished_at": utc_now().isoformat(),
            "sources_ok": sum(1 for s in self.sources if s["ok"]),
            "sources_total": len(self.sources),
            "checks_failed": len(self.failed_checks),
            "checks_total": len(self.checks),
            "status": "fail" if self.failed_checks else "ok",
        }
