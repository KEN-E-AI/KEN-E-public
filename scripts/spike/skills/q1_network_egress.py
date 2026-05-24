"""SK-PRD-00 Q1 — Network egress probe.

Empirically tests whether code running inside AgentEngineSandboxCodeExecutor
can exfiltrate data to arbitrary external endpoints.

Probes four egress vectors in sequence and prints one JSON line per probe
plus a final summary line.  Each probe is wrapped in a bare except so a
single failure cannot suppress later probes.

Vectors:
  dns     -- plain DNS resolution via socket.gethostbyname
  https   -- HTTPS GET to a public reflection service (httpbin.org/get)
  doh     -- DNS-over-HTTPS to Cloudflare (cloudflare-dns.com/dns-query)
  tcp_raw -- raw TCP connection to Cloudflare DNS resolver on port 53

Output format (one JSON object per line):
  {"vector": "dns", "target": "example.com", "outcome": "allowed",
   "details": "resolved to 93.184.216.34"}

Outcome values:
  allowed  -- connection succeeded; data reached the external endpoint
  blocked  -- socket/network layer rejected the connection
  partial  -- ambiguous (e.g. DNS resolves but TCP connect times out)
  error    -- unexpected exception unrelated to network policy

Summary line:
  {"vector": "summary", "allowed": N, "blocked": N, "partial": N, "error": N}

Run inside the sandbox (via sandbox_test_harness.py) to get empirical results:
  uv run python scripts/spike/sandbox_test_harness.py \\
      --script scripts/spike/skills/q1_network_egress.py

Run locally to verify the probe targets are reachable and the script is
structurally correct (does NOT measure sandbox behaviour):
  uv run python scripts/spike/skills/q1_network_egress.py --self-test

Note: the --self-test flag changes nothing about probe logic; it only adds
a header line so the operator knows the results reflect the host VM, not the
sandbox.  Local results MUST NOT be used as evidence for Q1 findings.

This file is on the throwaway spike/agent-engine-sandbox branch and is NEVER
merged to main (SK-PRD-00 §7 AC #1).
"""

from __future__ import annotations

import json
import socket
import sys
import traceback
import urllib.request

# ---------------------------------------------------------------------------
# Probe targets (IANA-reserved / stable public endpoints)
# ---------------------------------------------------------------------------
_DNS_HOST = "example.com"
_HTTPS_URL = "https://httpbin.org/get"
_DOH_URL = "https://cloudflare-dns.com/dns-query?name=example.com&type=A"
_TCP_HOST = "1.1.1.1"
_TCP_PORT = 53
_PROBE_TIMEOUT = 5  # seconds; short enough not to stall the sandbox session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _emit(record: dict) -> None:
    """Print a single JSON line and flush immediately.

    Immediate flush is important: Vertex sandboxes may truncate trailing stdout
    if the process ends before the OS flushes its stdio buffer.  Each probe
    writes independently so any missing lines are detectable.
    """
    print(json.dumps(record), flush=True)


def _probe_dns() -> dict:
    """Probe A: plain DNS resolution via socket.gethostbyname."""
    try:
        resolved = socket.gethostbyname(_DNS_HOST)
        return {
            "vector": "dns",
            "target": _DNS_HOST,
            "outcome": "allowed",
            "details": f"resolved to {resolved}",
        }
    except socket.gaierror as exc:
        return {
            "vector": "dns",
            "target": _DNS_HOST,
            "outcome": "blocked",
            "details": f"gaierror: {exc}",
        }
    except OSError as exc:
        return {
            "vector": "dns",
            "target": _DNS_HOST,
            "outcome": "error",
            "details": f"OSError: {exc}",
        }
    except Exception:
        return {
            "vector": "dns",
            "target": _DNS_HOST,
            "outcome": "error",
            "details": traceback.format_exc(limit=3).strip(),
        }


def _probe_https() -> dict:
    """Probe B: HTTPS GET to httpbin.org — confirms full HTTP stack works."""
    try:
        req = urllib.request.Request(
            _HTTPS_URL,
            headers={"User-Agent": "kene-sk-prd-00-spike/1.0"},
        )
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:
            status = resp.status
            # Read a small slice; we need only the status, not the body.
            body_preview = resp.read(256).decode("utf-8", errors="replace")
        return {
            "vector": "https",
            "target": _HTTPS_URL,
            "outcome": "allowed",
            "details": f"HTTP {status}; body_preview={body_preview[:80]!r}",
        }
    except urllib.error.URLError as exc:
        reason = exc.reason
        # URLError.reason may be an OSError (network blocked) or a string (HTTP error).
        outcome = "blocked" if isinstance(reason, OSError) else "error"
        return {
            "vector": "https",
            "target": _HTTPS_URL,
            "outcome": outcome,
            "details": f"URLError: {exc}",
        }
    except TimeoutError as exc:
        return {
            "vector": "https",
            "target": _HTTPS_URL,
            "outcome": "blocked",
            "details": f"TimeoutError: {exc}",
        }
    except Exception:
        return {
            "vector": "https",
            "target": _HTTPS_URL,
            "outcome": "error",
            "details": traceback.format_exc(limit=3).strip(),
        }


def _probe_doh() -> dict:
    """Probe C: DNS-over-HTTPS to Cloudflare.

    DoH uses port 443 and application/dns-json MIME type.  If plain DNS is
    blocked but HTTPS is allowed, DoH can bypass the DNS block — this probe
    tests that gap.
    """
    try:
        req = urllib.request.Request(
            _DOH_URL,
            headers={
                "Accept": "application/dns-json",
                "User-Agent": "kene-sk-prd-00-spike/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=_PROBE_TIMEOUT) as resp:
            status = resp.status
            body_preview = resp.read(256).decode("utf-8", errors="replace")
        return {
            "vector": "doh",
            "target": _DOH_URL,
            "outcome": "allowed",
            "details": f"HTTP {status}; body_preview={body_preview[:80]!r}",
        }
    except urllib.error.URLError as exc:
        reason = exc.reason
        outcome = "blocked" if isinstance(reason, OSError) else "error"
        return {
            "vector": "doh",
            "target": _DOH_URL,
            "outcome": outcome,
            "details": f"URLError: {exc}",
        }
    except TimeoutError as exc:
        return {
            "vector": "doh",
            "target": _DOH_URL,
            "outcome": "blocked",
            "details": f"TimeoutError: {exc}",
        }
    except Exception:
        return {
            "vector": "doh",
            "target": _DOH_URL,
            "outcome": "error",
            "details": traceback.format_exc(limit=3).strip(),
        }


def _probe_tcp_raw() -> dict:
    """Probe D: raw TCP to Cloudflare DNS on port 53.

    Tests whether the sandbox permits non-HTTP/S egress.  A successful
    connect() to port 53 on a known host demonstrates unrestricted TCP egress
    even to non-standard ports — the attack surface for data exfiltration via
    DNS or other side-channel techniques.
    """
    try:
        conn = socket.create_connection((_TCP_HOST, _TCP_PORT), timeout=_PROBE_TIMEOUT)
        conn.close()
        return {
            "vector": "tcp_raw",
            "target": f"{_TCP_HOST}:{_TCP_PORT}",
            "outcome": "allowed",
            "details": "create_connection() succeeded; port 53 reachable",
        }
    except ConnectionRefusedError as exc:
        # Port is accessible but actively refused — network is reachable.
        return {
            "vector": "tcp_raw",
            "target": f"{_TCP_HOST}:{_TCP_PORT}",
            "outcome": "partial",
            "details": f"ConnectionRefusedError: {exc}",
        }
    except TimeoutError as exc:
        return {
            "vector": "tcp_raw",
            "target": f"{_TCP_HOST}:{_TCP_PORT}",
            "outcome": "blocked",
            "details": f"Timeout: {exc}",
        }
    except OSError as exc:
        return {
            "vector": "tcp_raw",
            "target": f"{_TCP_HOST}:{_TCP_PORT}",
            "outcome": "blocked",
            "details": f"OSError: {exc}",
        }
    except Exception:
        return {
            "vector": "tcp_raw",
            "target": f"{_TCP_HOST}:{_TCP_PORT}",
            "outcome": "error",
            "details": traceback.format_exc(limit=3).strip(),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    self_test = "--self-test" in sys.argv

    if self_test:
        print(
            json.dumps({
                "vector": "meta",
                "context": "self-test",
                "note": (
                    "Running outside sandbox — results reflect host VM reachability, "
                    "NOT sandbox egress policy.  Do not cite these as Q1 evidence."
                ),
            }),
            flush=True,
        )

    results = [
        _probe_dns(),
        _probe_https(),
        _probe_doh(),
        _probe_tcp_raw(),
    ]

    counts: dict[str, int] = {"allowed": 0, "blocked": 0, "partial": 0, "error": 0}
    for r in results:
        _emit(r)
        outcome = r.get("outcome", "error")
        counts[outcome] = counts.get(outcome, 0) + 1

    _emit({"vector": "summary", **counts})


if __name__ == "__main__":
    main()
