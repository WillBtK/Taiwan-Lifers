#!/usr/bin/env python3
"""Fetch the sources that need an egress this sandbox does not have.

Run by .github/workflows/fetch-sources.yml on a GitHub runner, which reaches
things the agent sandbox cannot (and vice versa — see docs/decisions.md 4.13
for the measured matrix). Writes each payload verbatim to
data/raw/<source>/<name>_YYYYMMDD.<ext>, the same shape the couriered files
took, so the existing loaders read either without modification.

Deduplicates on content: if the newest existing snapshot of a source is byte
identical, nothing is written, so the repository accumulates one file per
actual revision rather than one per run.

ins-info.ib.gov.tw refuses every egress available to CI. Those URLs are
fetched through a relay with Taiwan egress when TAIWAN_RELAY_URL is set
(ops/taiwan-relay), and skipped with a recorded reason when it is not. A
missing relay is not a failure: the workflow still succeeds and the report
says which sources were unavailable.
"""
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CERT = ROOT / "config" / "certs" / "twca_secure_ssl_ca.pem"
UA = "Mozilla/5.0 (compatible; TLFX/1.0; +https://github.com/WillBtK/Taiwan-Lifers)"

# name, url, subdirectory, extension, needs_relay, needs_twca_cert
SOURCES = [
    ("tigf_holdings",
     "https://www.tigf.org.tw/content/2025/file/"
     "%E4%BF%9D%E9%9A%AA%E6%A5%AD%E6%8A%95%E8%B3%87%E5%9C%8B%E5%85%A7%E5%A4%96"
     "%E8%82%A1%E7%A5%A8%E5%8F%8A%E5%82%B5%E5%88%B8%E9%87%91%E9%A1%8D.csv",
     "tigf", "csv", False, False),
    ("FSI_life",
     "https://www.cbc.gov.tw/public/data/opendata/financialstability/"
     "FSI-%E5%A3%BD%E9%9A%AA%E5%85%AC%E5%8F%B8.csv",
     "cbc", "csv", False, False),
    ("tii_I171", "https://openapi.tii.org.tw/TIIOPENDATA/API/CSV_EXPORT?TableID=I171",
     "tii", "csv", False, True),
    ("tii_K47", "https://openapi.tii.org.tw/TIIOpenData/API/CSV_EXPORT?TableID=K47",
     "tii", "csv", False, True),
    ("json-06161610", "https://ins-info.ib.gov.tw/opendata/json-06161610.aspx",
     "ins-info", "json", True, False),
    ("json-06021011", "https://ins-info.ib.gov.tw/opendata/json-06021011.aspx",
     "ins-info", "json", True, False),
    # The other seven aggregate tables, found by walking the portal's report
    # menu (decisions 4.26). json-<code>.aspx holds for every 彙計表 code.
    ("json-05010111", "https://ins-info.ib.gov.tw/opendata/json-05010111.aspx",
     "ins-info", "json", True, False),      # 公司基本資料
    ("json-05020511", "https://ins-info.ib.gov.tw/opendata/json-05020511.aspx",
     "ins-info", "json", True, False),      # 內部人員數
    ("json-05030310", "https://ins-info.ib.gov.tw/opendata/json-05030310.aspx",
     "ins-info", "json", True, False),      # 股東持股
    ("json-05030311", "https://ins-info.ib.gov.tw/opendata/json-05030311.aspx",
     "ins-info", "json", True, False),      # 股權異動
    ("json-06161601", "https://ins-info.ib.gov.tw/opendata/json-06161601.aspx",
     "ins-info", "json", True, False),      # 產險財務業務指標
    ("json-07010801", "https://ins-info.ib.gov.tw/opendata/json-07010801.aspx",
     "ins-info", "json", True, False),      # 產險業務概況
    ("json-07011010", "https://ins-info.ib.gov.tw/opendata/json-07011010.aspx",
     "ins-info", "json", True, False),      # 壽險業務概況
    ("json-07090901", "https://ins-info.ib.gov.tw/opendata/json-07090901.aspx",
     "ins-info", "json", True, False),      # 申訴率統計
]

# Per-company disclosures. These are the reason the relay was built: the
# aggregate tables above are sector-wide, but Info2-1 is FUND UTILISATION PER
# FIRM -- 國外投資 by insurer, the hedge-ratio denominator the project has only
# ever had at sector level or from investor decks. Info2-5 and Info2-14 are the
# reserve pages, which may split 特別盈餘公積 into its FX-designated buckets and
# so close the question decisions 4.19 could only bound.
#
# Pages are Big5 HTML, ~20-130KB each, addressed by 統一編號 (config/firm_uids.tsv).
FIRM_PAGES = [("Info2-1", "資金運用表"), ("Info2-5", "準備金"),
              ("Info2-14", "其他負債項下之特別準備及其他準備")]


def firm_sources():
    path = ROOT / "config" / "firm_uids.tsv"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or line.startswith("entity_id\t"):
            continue
        parts = line.split("\t")
        entity, uid = parts[0].strip(), parts[1].strip()
        for page, _label in FIRM_PAGES:
            out.append((f"{page}_{entity}",
                        f"https://ins-info.ib.gov.tw/customer/{page}.aspx?UID={uid}",
                        "ins-info-firm", "html", True, False))
    return out


SOURCES += firm_sources()


def ssl_context(needs_cert):
    """Default trust store, plus the TWCA intermediate where a host omits it.

    Passing cafile= to create_default_context REPLACES the trust store, which
    fails: the TWCA file holds the intermediate the server should have sent,
    not the root that signs it. It has to be added to the defaults.
    """
    import ssl
    ctx = ssl.create_default_context()
    if needs_cert and CERT.exists():
        ctx.load_verify_locations(cafile=str(CERT))
    return ctx


def _relay_get(base, token, url):
    req = urllib.request.Request(
        base.rstrip("/") + "/fetch?url=" + urllib.parse.quote(url, safe=""),
        headers={"User-Agent": UA})
    if token:
        req.add_header("X-Relay-Token", token)
    return req


def _relay_post(base, token, url):
    """The same request as a POST with the target in the body.

    The relay's /health advertises "post": true, and a rebuilt relay that moved
    /fetch to POST answers a GET with 403 rather than 405 — which is
    indistinguishable, from the client, from a token that no longer matches.
    """
    req = urllib.request.Request(
        base.rstrip("/") + "/fetch",
        data=json.dumps({"url": url}).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json"})
    if token:
        req.add_header("X-Relay-Token", token)
    return req


def _relay_bearer(base, token, url):
    """The third possibility: the token moved to a standard Authorization.

    Sent as its own attempt rather than added to the others, because a Cloud
    Run service that does enforce IAM would reject an Authorization it cannot
    validate and turn a legible 403 into a misleading 401.
    """
    req = urllib.request.Request(
        base.rstrip("/") + "/fetch?url=" + urllib.parse.quote(url, safe=""),
        headers={"User-Agent": UA})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    return req


def fetch(url, needs_relay, needs_cert, timeout=60):
    """Return bytes, or raise. Relay-bound URLs go through the Taiwan relay."""
    if not needs_relay:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout,
                                    context=ssl_context(needs_cert)) as r:
            return r.read()
    base = os.environ.get("TAIWAN_RELAY_URL", "").strip()
    if not base:
        raise RuntimeError(
            "no TAIWAN_RELAY_URL configured (Taiwan egress unavailable)")
    token = os.environ.get("TAIWAN_RELAY_TOKEN", "").strip()
    ctx = ssl_context(False)
    # Three shapes, all reported. A rejected token, a /fetch that has moved to
    # POST and a token that has moved to Authorization are one 403 each from
    # the client's side, and every ins-info source failed that way while the
    # relay's own /health answered ok with ins-info on its allow list. Trying
    # all three and printing every code settles which in one run rather than
    # one run per guess. The bodies are the relay's, not the origin's, and
    # carry no credential.
    tried = []
    for build in (_relay_get, _relay_post, _relay_bearer):
        label = build.__name__[7:]
        try:
            with urllib.request.urlopen(build(base, token, url),
                                        timeout=timeout, context=ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            try:
                detail = e.read()[:120].decode("utf-8", "replace").strip()
            except Exception:                                # noqa: BLE001
                detail = ""
            tried.append(f"{label} {e.code} {detail or e.reason}")
            if e.code not in (401, 403, 404, 405):
                break
        except Exception as e:                               # noqa: BLE001
            tried.append(f"{label} {type(e).__name__}: {e}")
            break
    raise RuntimeError("relay refused: " + "; ".join(tried))


def newest_existing(d, name, ext):
    # sorted() puts "name_20260905-2.ext" after "name_20260905.ext", so the
    # newest same-day variant wins the comparison, which is what dedupe wants
    files = sorted(d.glob(f"{name}_*.{ext}"))
    return files[-1] if files else None


def main():
    stamp = dt.date.today().strftime("%Y%m%d")
    report = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(), "sources": []}
    written = unchanged = unavailable = 0

    for name, url, sub, ext, relay, cert in SOURCES:
        entry = {"name": name, "url": url, "needs_relay": relay}
        try:
            body = fetch(url, relay, cert)
        except Exception as e:
            entry.update(status="unavailable", error=f"{type(e).__name__}: {e}")
            report["sources"].append(entry)
            unavailable += 1
            print(f"UNAVAILABLE {name}: {e}")
            continue

        if not body.strip():
            entry.update(status="empty")
            report["sources"].append(entry)
            unavailable += 1
            print(f"EMPTY       {name}")
            continue

        digest = hashlib.sha256(body).hexdigest()
        d = ROOT / "data" / "raw" / sub
        d.mkdir(parents=True, exist_ok=True)
        prev = newest_existing(d, name, ext)
        if prev and hashlib.sha256(prev.read_bytes()).hexdigest() == digest:
            entry.update(status="unchanged", sha256=digest, matches=prev.name)
            unchanged += 1
            print(f"UNCHANGED   {name} (== {prev.name})")
        else:
            # Never clobber an existing snapshot that shares today's stamp but
            # differs in content. That case is not a re-fetch, it is two
            # different observations of the same day -- a hand-couriered file
            # and an automated one, or a source that changed mid-day -- and
            # destroying either loses the provenance that justifies the row.
            path = d / f"{name}_{stamp}.{ext}"
            n = 1
            while path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                n += 1
                path = d / f"{name}_{stamp}-{n}.{ext}"
            path.write_bytes(body)
            entry.update(status="written", sha256=digest, bytes=len(body),
                         path=str(path.relative_to(ROOT)))
            written += 1
            print(f"WRITTEN     {name} -> {path.relative_to(ROOT)} ({len(body):,} bytes)")
        report["sources"].append(entry)

    report["summary"] = {"written": written, "unchanged": unchanged,
                         "unavailable": unavailable}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "fetch_sources_latest.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwritten {written}, unchanged {unchanged}, unavailable {unavailable}")
    # An unavailable relay-bound source is expected until the relay exists, so
    # it must not fail the run; a source that should be reachable and is not is
    # worth failing on, because that is a regression worth seeing.
    hard = [s for s in report["sources"]
            if s["status"] == "unavailable" and not s["needs_relay"]]
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
