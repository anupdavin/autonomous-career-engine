"""Unit tests for dashboard slice routes, private access security, and operational runbook."""

import json
import os
import re
import sqlite3
import tempfile
from typing import Any
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from app_server import (
    CURATED_TABLES,
    PrivateAccessSecurityMiddleware,
    get_allowed_hosts,
    get_allowed_origins,
    parse_host_header,
    resolve_curated_status_filter_column,
    sanitize_curated_value,
)


class TestPureResolversAndSanitizers(unittest.TestCase):
    def test_resolve_curated_status_filter_column_memories(self) -> None:
        mem_cols = ["job_id", "lifecycle_stage", "work_location_status"]
        for stage in ("SHORTLISTED", "APPROVED", "APPLIED", "INTERVIEW", "OFFER", "DEAD_ZONE"):
            col = resolve_curated_status_filter_column("agent_episodic_memories", stage, mem_cols)
            self.assertEqual(col, "lifecycle_stage", f"Stage {stage} should map to lifecycle_stage")
            # Case-insensitivity check
            col_lower = resolve_curated_status_filter_column("agent_episodic_memories", stage.lower(), mem_cols)
            self.assertEqual(col_lower, "lifecycle_stage", f"Lowercase stage {stage} should map to lifecycle_stage")

        for loc in ("VERIFIED", "NEEDS_REVIEW", "INELIGIBLE"):
            col = resolve_curated_status_filter_column("agent_episodic_memories", loc, mem_cols)
            self.assertEqual(col, "work_location_status", f"Location {loc} should map to work_location_status")
            col_lower = resolve_curated_status_filter_column("agent_episodic_memories", loc.lower(), mem_cols)
            self.assertEqual(col_lower, "work_location_status", f"Lowercase location {loc} should map to work_location_status")

    def test_resolve_curated_status_filter_column_runs_and_timeline(self) -> None:
        for status in ("SUCCESS", "RUNNING", "FAILED", "STALE"):
            col = resolve_curated_status_filter_column("agent_runs", status, ["run_id", "status"])
            self.assertEqual(col, "status")

        for stage in ("APPROVED", "APPLIED", "INTERVIEW"):
            col = resolve_curated_status_filter_column("application_timeline_events", stage, ["event_id", "to_stage"])
            self.assertEqual(col, "to_stage")

    def test_curated_columns_and_whitelist(self) -> None:
        # agent_runs must NOT expose summary
        run_cols = CURATED_TABLES["agent_runs"]["columns"]
        self.assertNotIn("summary", run_cols)
        expected_run_cols = ["run_id", "workflow", "status", "phase", "started_at", "updated_at", "finished_at"]
        self.assertEqual(run_cols, expected_run_cols)

        # Sensitive internal tables must not be present
        self.assertNotIn("resume_vault_versions", CURATED_TABLES)
        self.assertNotIn("human_feedback_events", CURATED_TABLES)
        self.assertNotIn("sqlite_master", CURATED_TABLES)

    def test_url_and_tunnel_sanitization_helper(self) -> None:
        raw_text = "Visit https://job.com or http://test.trycloudflare.com or mail tester@example.test"
        cleaned = sanitize_curated_value(raw_text)
        self.assertNotIn("https://job.com", cleaned)
        self.assertNotIn("trycloudflare.com", cleaned)
        self.assertNotIn("tester@example.test", cleaned)
        self.assertIn("[REDACTED_URL]", cleaned)
        self.assertIn("[REDACTED_EMAIL]", cleaned)


class TestDashboardHtmlRequirements(unittest.TestCase):
    def setUp(self) -> None:
        self.html_path = Path(__file__).resolve().parent.parent / "dashboard_ui.html"
        self.assertTrue(self.html_path.exists(), "dashboard_ui.html must exist")
        self.html_content = self.html_path.read_text(encoding="utf-8")

    def test_zero_em_and_en_dashes(self) -> None:
        for code, name in [(0x2014, "em-dash"), (0x2013, "en-dash"), (0x2015, "horizontal bar")]:
            count = self.html_content.count(chr(code))
            self.assertEqual(count, 0, f"Found {count} {name} characters in dashboard_ui.html")

        for entity in ["&m" + "dash;", "&n" + "dash;"]:
            count = self.html_content.count(entity)
            self.assertEqual(count, 0, f"Found {count} {entity} entities in dashboard_ui.html")

    def test_local_preparation_and_human_controlled_labeling(self) -> None:
        self.assertIn("Prepare Materials (Local Only)", self.html_content)
        self.assertIn("Human-Controlled", self.html_content)
        self.assertIn('id="prepareMaterialsBtn"', self.html_content)
        self.assertIn('/api/prepare-materials', self.html_content)
        self.assertNotIn('id="autoApplyBtn"', self.html_content)
        self.assertNotIn('/api/auto-apply', self.html_content)
        self.assertNotIn("triggerAutoApply", self.html_content)

    def test_keyboard_accessibility_and_aria_attributes(self) -> None:
        self.assertIn('role="tablist"', self.html_content)
        self.assertIn('role="tab"', self.html_content)
        self.assertIn('role="tabpanel"', self.html_content)
        self.assertIn('aria-selected=', self.html_content)
        self.assertIn('aria-controls=', self.html_content)
        self.assertIn(':focus-visible', self.html_content)
        self.assertIn('tabindex="0"', self.html_content)
        self.assertIn('role="region"', self.html_content)

    def test_responsive_layout_media_queries(self) -> None:
        self.assertIn("@media (max-width: 1024px)", self.html_content)
        self.assertIn("@media (max-width: 768px)", self.html_content)
        self.assertIn("@media (max-width: 480px)", self.html_content)

    def test_private_access_badge_present(self) -> None:
        self.assertIn("Private Access (127.0.0.1)", self.html_content)

    def test_csrf_tokens_on_all_post_calls(self) -> None:
        self.assertIn("function getCsrfToken()", self.html_content)
        self.assertIn("app_csrf", self.html_content)
        self.assertIn("'X-CSRF-Token': getCsrfToken()", self.html_content)


class TestSecureCloudflareTunnelRunbook(unittest.TestCase):
    def setUp(self) -> None:
        self.runbook_path = Path(__file__).resolve().parent.parent / "docs" / "operations" / "secure-cloudflare-tunnel.md"
        self.assertTrue(self.runbook_path.exists(), "secure-cloudflare-tunnel.md must exist")
        self.content = self.runbook_path.read_text(encoding="utf-8")

    def test_zero_em_and_en_dashes(self) -> None:
        for code, name in [(0x2014, "em-dash"), (0x2013, "en-dash"), (0x2015, "horizontal bar")]:
            count = self.content.count(chr(code))
            self.assertEqual(count, 0, f"Found {count} {name} characters in secure-cloudflare-tunnel.md")

        for entity in ["&m" + "dash;", "&n" + "dash;"]:
            count = self.content.count(entity)
            self.assertEqual(count, 0, f"Found {count} {entity} entities in secure-cloudflare-tunnel.md")

    def test_required_placeholders_present(self) -> None:
        placeholders = [
            "[APPROVED_IDENTITY_OR_GROUP]",
            "[TEAM_NAME]",
            "[POSTURE_POLICY]",
            "[HOSTNAME]",
            "[TUNNEL_ID]",
            "[AUD_TAG]",
        ]
        for p in placeholders:
            self.assertIn(p, self.content, f"Placeholder {p} must be present in runbook")

    def test_core_security_sections_present(self) -> None:
        # Loopback binding invariant
        self.assertIn("127.0.0.1:8080", self.content)
        self.assertIn("0.0.0.0", self.content)

        # Environment variables
        self.assertIn("APP_ALLOWED_HOSTS", self.content)
        self.assertIn("APP_ALLOWED_ORIGINS", self.content)
        self.assertIn("APP_CSRF_COOKIE_SECURE", self.content)

        # Zero Trust Access
        self.assertIn("Cloudflare Zero Trust Access", self.content)
        self.assertIn("Default-Deny Policy", self.content)
        self.assertIn("Cf-Access-Jwt-Assertion", self.content)

        # Connector origin validation boundary
        self.assertIn("originRequest", self.content)
        self.assertIn("teamName", self.content)
        self.assertIn("audTag", self.content)

        # Windows service installation
        self.assertIn("cloudflared service install", self.content)
        self.assertIn("Start-Service cloudflared", self.content)

        # Emergency procedures
        self.assertIn("Emergency Procedures & Killswitch", self.content)
        self.assertIn("Stop-Service cloudflared", self.content)

        # Quick tunnel prohibition
        self.assertIn("trycloudflare.com", self.content)


def make_synthetic_app() -> Any:
    async def synthetic_downstream(scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            return
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        if method == "GET" and path == "/":
            resp = JSONResponse({"status": "index_ok"})
        elif method in ("GET", "HEAD", "OPTIONS") and path == "/api/synthetic-read":
            resp = JSONResponse({"status": "read_ok"})
        elif method not in ("GET", "HEAD", "OPTIONS") and path == "/api/synthetic-mutate":
            resp = JSONResponse({"status": "mutate_ok"})
        else:
            resp = JSONResponse({"status": "not_found"}, status_code=404)
        await resp(scope, receive, send)

    return PrivateAccessSecurityMiddleware(synthetic_downstream)


class TestPrivateAccessSecurityMiddleware(unittest.TestCase):
    def test_parse_host_header_valid_and_malformed(self) -> None:
        # Valid hostnames and bracketed IPv6 with valid decimal ports (1-65535)
        self.assertEqual(parse_host_header("127.0.0.1:8080"), "127.0.0.1")
        self.assertEqual(parse_host_header("127.0.0.1"), "127.0.0.1")
        self.assertEqual(parse_host_header("localhost:8080"), "localhost")
        self.assertEqual(parse_host_header("localhost"), "localhost")
        self.assertEqual(parse_host_header("[::1]:8080"), "::1")
        self.assertEqual(parse_host_header("[::1]"), "::1")
        self.assertEqual(parse_host_header("[0:0:0:0:0:0:0:1]:8080"), "::1")
        self.assertEqual(parse_host_header("[0:0:0:0:0:0:0:1]"), "::1")
        self.assertEqual(parse_host_header("[2001:0db8:0000:0000:0000:0000:0000:0001]:443"), "2001:db8::1")
        self.assertEqual(parse_host_header("[2001:db8::1]"), "2001:db8::1")
        self.assertEqual(parse_host_header("127.0.0.1:1"), "127.0.0.1")
        self.assertEqual(parse_host_header("127.0.0.1:65535"), "127.0.0.1")
        self.assertEqual(parse_host_header("tunnel.example.com:443"), "tunnel.example.com")
        self.assertEqual(parse_host_header("my-tunnel.example.com"), "my-tunnel.example.com")

        # Valid maximum-length label (63 chars) and hostname (253 chars)
        max_label_host = ("a" * 63) + ".example.com"
        self.assertEqual(parse_host_header(max_label_host), max_label_host)
        valid_253 = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 61
        self.assertEqual(len(valid_253), 253)
        self.assertEqual(parse_host_header(valid_253), valid_253)

        # Malformed host syntax, invalid ports, and forbidden characters fail closed
        self.assertEqual(parse_host_header(""), "")
        self.assertEqual(parse_host_header("127.0.0.1:0"), "")
        self.assertEqual(parse_host_header("127.0.0.1:65536"), "")
        self.assertEqual(parse_host_header("127.0.0.1:-80"), "")
        self.assertEqual(parse_host_header("127.0.0.1:abc"), "")
        self.assertEqual(parse_host_header("127.0.0.1:8080/path"), "")
        self.assertEqual(parse_host_header("127.0.0.1?query"), "")
        self.assertEqual(parse_host_header("127.0.0.1#hash"), "")
        self.assertEqual(parse_host_header("attacker.com@127.0.0.1"), "")
        self.assertEqual(parse_host_header(" 127.0.0.1"), "")
        self.assertEqual(parse_host_header("127.0.0.1 "), "")
        self.assertEqual(parse_host_header("127.0.0.1: 8080"), "")
        self.assertEqual(parse_host_header("127.0.0.1\r\n"), "")
        self.assertEqual(parse_host_header("[::1]:"), "")
        self.assertEqual(parse_host_header("[::1]extra"), "")
        self.assertEqual(parse_host_header("127.0.0.1:80:80"), "")
        self.assertEqual(parse_host_header("..badhost"), "")
        self.assertEqual(parse_host_header(".badhost"), "")
        self.assertEqual(parse_host_header("badhost."), "")
        self.assertEqual(parse_host_header("sub..badhost.com"), "")

        # Malformed DNS labels (leading/trailing hyphen, invalid punctuation)
        self.assertEqual(parse_host_header("-bad.example.com"), "")
        self.assertEqual(parse_host_header("bad-.example.com"), "")
        self.assertEqual(parse_host_header("sub.-bad.example.com"), "")
        self.assertEqual(parse_host_header("sub.bad-.example.com"), "")
        self.assertEqual(parse_host_header("sub.-.example.com"), "")
        self.assertEqual(parse_host_header("-localhost"), "")
        self.assertEqual(parse_host_header("localhost-"), "")
        self.assertEqual(parse_host_header("sub_domain.example.com"), "")

        # Overlong DNS label (>63 characters) and overlong hostname (>253 characters)
        self.assertEqual(parse_host_header(("a" * 64) + ".example.com"), "")
        overlong_254 = "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 62
        self.assertEqual(len(overlong_254), 254)
        self.assertEqual(parse_host_header(overlong_254), "")
        self.assertEqual(parse_host_header(("a" * 63 + ".") * 4 + "com"), "")

        # Malformed bracketed IPv6 literals fail closed
        self.assertEqual(parse_host_header("[:::1]"), "")
        self.assertEqual(parse_host_header("[127.0.0.1]"), "")
        self.assertEqual(parse_host_header("[not:ipv6]"), "")
        self.assertEqual(parse_host_header("[2001:db8:::1]"), "")
        self.assertEqual(parse_host_header("[]"), "")
        self.assertEqual(parse_host_header("[fe80::1%eth0]"), "")

        # Malformed Unicode digit ports fail closed for IPv4 and bracketed IPv6
        self.assertEqual(parse_host_header("127.0.0.1:\u00b2"), "")
        self.assertEqual(parse_host_header("127.0.0.1:\u00b3"), "")
        self.assertEqual(parse_host_header("127.0.0.1:\u0660"), "")
        self.assertEqual(parse_host_header("127.0.0.1:\uff18\uff10\uff18\uff10"), "")
        self.assertEqual(parse_host_header("127.0.0.1:80\u00b2"), "")
        self.assertEqual(parse_host_header("[::1]:\u00b2"), "")
        self.assertEqual(parse_host_header("[::1]:\u00b3"), "")
        self.assertEqual(parse_host_header("[::1]:\u0660"), "")
        self.assertEqual(parse_host_header("[::1]:\uff18\uff10\uff18\uff10"), "")
        self.assertEqual(parse_host_header("[::1]:80\u00b2"), "")

    def test_default_allowed_hosts_and_origins(self) -> None:
        hosts = get_allowed_hosts()
        self.assertIn("127.0.0.1", hosts)
        self.assertIn("localhost", hosts)
        self.assertIn("::1", hosts)
        self.assertNotIn("testserver", hosts)

        origins = get_allowed_origins()
        self.assertIn("http://127.0.0.1:8080", origins)
        self.assertIn("http://localhost:8080", origins)
        self.assertNotIn("http://testserver", origins)

        # APP_ALLOWED_HOSTS normalizes bracketed IPv6 and ignores malformed literals
        with patch.dict(os.environ, {"APP_ALLOWED_HOSTS": "[0:0:0:0:0:0:0:1]:8080, [2001:0db8::1], [:::1]"}):
            configured_hosts = get_allowed_hosts()
            self.assertIn("::1", configured_hosts)
            self.assertIn("2001:db8::1", configured_hosts)
            self.assertNotIn(":::1", configured_hosts)

    def test_unauthorized_and_malformed_host_cookie_behavior(self) -> None:
        client = TestClient(make_synthetic_app(), base_url="http://127.0.0.1:8080")

        # Unauthorized Host on GET / must return 403 and NOT set app_csrf
        resp_unauth = client.get("/", headers={"Host": "untrusted-attacker.com"})
        self.assertEqual(resp_unauth.status_code, 403)
        self.assertNotIn("app_csrf", resp_unauth.cookies)
        self.assertNotIn("set-cookie", resp_unauth.headers)
        self.assertIn("untrusted Host", resp_unauth.json().get("error", ""))

        # Malformed Host on GET / must return 403 and NOT set app_csrf
        resp_malformed = client.get("/", headers={"Host": "127.0.0.1:0"})
        self.assertEqual(resp_malformed.status_code, 403)
        self.assertNotIn("app_csrf", resp_malformed.cookies)
        self.assertNotIn("set-cookie", resp_malformed.headers)

        # Invalid out-of-range port in Host header must return 403 (not 500) and NOT set app_csrf
        resp_invalid_port_ipv4 = client.get("/", headers={"Host": "127.0.0.1:65536"})
        self.assertEqual(resp_invalid_port_ipv4.status_code, 403)
        self.assertNotIn("app_csrf", resp_invalid_port_ipv4.cookies)

        resp_invalid_port_ipv6 = client.get("/", headers={"Host": "[::1]:65536"})
        self.assertEqual(resp_invalid_port_ipv6.status_code, 403)
        self.assertNotIn("app_csrf", resp_invalid_port_ipv6.cookies)

        # Authorized Host on GET / returns 200 and issues app_csrf cookie
        resp_ok = client.get("/", headers={"Host": "127.0.0.1:8080"})
        self.assertEqual(resp_ok.status_code, 200)
        self.assertIn("app_csrf", resp_ok.cookies)
        self.assertEqual(resp_ok.headers.get("x-frame-options"), "DENY")
        self.assertEqual(resp_ok.headers.get("x-content-type-options"), "nosniff")
        self.assertEqual(resp_ok.json(), {"status": "index_ok"})

    def test_unsafe_methods_and_exact_origin_rejection(self) -> None:
        client = TestClient(make_synthetic_app(), base_url="http://127.0.0.1:8080")

        # Safe methods (GET, HEAD, OPTIONS) do not require Origin or CSRF
        resp_get = client.get("/api/synthetic-read", headers={"Host": "127.0.0.1:8080"})
        self.assertEqual(resp_get.status_code, 200)

        resp_options = client.options("/api/synthetic-read", headers={"Host": "127.0.0.1:8080"})
        self.assertEqual(resp_options.status_code, 200)

        # Missing Origin header on unsafe method must be rejected
        resp_missing_origin = client.post(
            "/api/synthetic-mutate",
            headers={"Host": "127.0.0.1:8080"},
            json={},
        )
        self.assertEqual(resp_missing_origin.status_code, 403)
        self.assertIn("Origin", resp_missing_origin.json().get("error", ""))

        # Exact Origin check: trailing slash must be rejected
        resp_slash = client.post(
            "/api/synthetic-mutate",
            headers={"Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080/"},
            json={},
        )
        self.assertEqual(resp_slash.status_code, 403)
        self.assertIn("Origin", resp_slash.json().get("error", ""))

        # Padded Origin headers must be rejected (exact unstripped match)
        resp_leading_space = client.post(
            "/api/synthetic-mutate",
            headers={"Host": "127.0.0.1:8080", "Origin": " http://127.0.0.1:8080"},
            json={},
        )
        self.assertEqual(resp_leading_space.status_code, 403)
        self.assertIn("Origin", resp_leading_space.json().get("error", ""))

        resp_trailing_space = client.post(
            "/api/synthetic-mutate",
            headers={"Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080 "},
            json={},
        )
        self.assertEqual(resp_trailing_space.status_code, 403)
        self.assertIn("Origin", resp_trailing_space.json().get("error", ""))

        # Mismatched CSRF tokens must be rejected
        resp_mismatched_csrf = client.post(
            "/api/synthetic-mutate",
            headers={
                "Host": "127.0.0.1:8080",
                "Origin": "http://127.0.0.1:8080",
                "X-CSRF-Token": "token-submitted-in-header",
            },
            cookies={"app_csrf": "token-present-in-cookie"},
            json={},
        )
        self.assertEqual(resp_mismatched_csrf.status_code, 403)
        self.assertIn("CSRF", resp_mismatched_csrf.json().get("error", ""))

        # Missing header token with cookie present must be rejected
        resp_missing_header_csrf = client.post(
            "/api/synthetic-mutate",
            headers={
                "Host": "127.0.0.1:8080",
                "Origin": "http://127.0.0.1:8080",
            },
            cookies={"app_csrf": "token-present-in-cookie"},
            json={},
        )
        self.assertEqual(resp_missing_header_csrf.status_code, 403)
        self.assertIn("CSRF", resp_missing_header_csrf.json().get("error", ""))

        # Missing cookie with header token present must be rejected
        resp_missing_cookie_csrf = client.post(
            "/api/synthetic-mutate",
            headers={
                "Host": "127.0.0.1:8080",
                "Origin": "http://127.0.0.1:8080",
                "X-CSRF-Token": "token-submitted-in-header",
            },
            json={},
        )
        self.assertEqual(resp_missing_cookie_csrf.status_code, 403)
        self.assertIn("CSRF", resp_missing_cookie_csrf.json().get("error", ""))

        # Every unsafe method outside GET, HEAD, OPTIONS requires Origin and CSRF
        for unsafe_method in ("post", "put", "delete", "patch"):
            resp_missing_csrf = client.request(
                unsafe_method.upper(),
                "/api/synthetic-mutate",
                headers={"Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080"},
                json={},
            )
            self.assertEqual(resp_missing_csrf.status_code, 403, f"{unsafe_method} must reject missing CSRF")
            self.assertIn("CSRF", resp_missing_csrf.json().get("error", ""))

        # Uncommon unsafe method TRACE: rejected without Origin
        resp_trace_no_origin = client.request(
            "TRACE",
            "/api/synthetic-mutate",
            headers={"Host": "127.0.0.1:8080"},
        )
        self.assertEqual(resp_trace_no_origin.status_code, 403)
        self.assertIn("Origin", resp_trace_no_origin.json().get("error", ""))

        # Uncommon unsafe method TRACE: rejected without CSRF
        resp_trace_no_csrf = client.request(
            "TRACE",
            "/api/synthetic-mutate",
            headers={
                "Host": "127.0.0.1:8080",
                "Origin": "http://127.0.0.1:8080",
            },
        )
        self.assertEqual(resp_trace_no_csrf.status_code, 403)
        self.assertIn("CSRF", resp_trace_no_csrf.json().get("error", ""))

        # Uncommon unsafe method TRACE: allowed with valid Origin and matching CSRF
        trace_token = "synthetic-trace-token-abc"
        resp_trace_valid = client.request(
            "TRACE",
            "/api/synthetic-mutate",
            headers={
                "Host": "127.0.0.1:8080",
                "Origin": "http://127.0.0.1:8080",
                "X-CSRF-Token": trace_token,
            },
            cookies={"app_csrf": trace_token},
        )
        self.assertEqual(resp_trace_valid.status_code, 200)
        self.assertEqual(resp_trace_valid.json(), {"status": "mutate_ok"})

        # Exact allowed Origin + valid matching CSRF token passes to synthetic downstream
        token = "test-csrf-token-12345"
        resp_valid = client.post(
            "/api/synthetic-mutate",
            headers={
                "Host": "127.0.0.1:8080",
                "Origin": "http://127.0.0.1:8080",
                "X-CSRF-Token": token,
            },
            cookies={"app_csrf": token},
            json={"synthetic_key": "synthetic_val"},
        )
        self.assertEqual(resp_valid.status_code, 200)
        self.assertEqual(resp_valid.json(), {"status": "mutate_ok"})


if __name__ == "__main__":
    unittest.main()
