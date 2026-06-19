"""Validation suite (PRD §8). Uses stdlib unittest only (offline, no deps).

Run: python -m unittest discover -s tests
"""
import json
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path

# Make the package importable without installation.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_usage_dashboard import scanner, verify  # noqa: E402
from ai_usage_dashboard.aggregate import aggregate  # noqa: E402
from ai_usage_dashboard.config import Config  # noqa: E402
from ai_usage_dashboard.cost_engine import apply_costs, compute_cost  # noqa: E402
from ai_usage_dashboard.models import CostStatus  # noqa: E402
from ai_usage_dashboard.offline import NetworkAccessError, network_disabled  # noqa: E402
from ai_usage_dashboard.pricing import PricingTable  # noqa: E402
from ai_usage_dashboard.report import run_scan, write_report  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "sources"
CLAUDE = FIXTURES / ".claude"


def make_config(output_dir):
    return Config(
        read_paths=[CLAUDE],
        codex_paths=[FIXTURES / ".codex"],
        skills_paths=[CLAUDE / "skills"],
        output_dir=Path(output_dir),
    )


def sessions_by_id(sessions):
    return {s.session_id: s for s in sessions}


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self.sessions, self.warnings, self.failed = scanner.scan(
            Config(read_paths=[CLAUDE], output_dir="/tmp/ai-usage-dashboard")
        )
        self.by_id = sessions_by_id(self.sessions)

    def test_valid_session_tokens_summed(self):
        s = self.by_id["sess-valid"]
        self.assertEqual(s.model, "claude-opus-4-8")
        self.assertEqual(s.input_tokens, 2000)
        self.assertEqual(s.output_tokens, 500)
        self.assertEqual(s.day, "2026-06-15")

    def test_no_tokens_session_marked(self):
        s = self.by_id["sess-notok"]
        self.assertFalse(s.has_tokens)

    def test_corrupt_file_does_not_abort_and_warns(self):
        # The corrupt file still yields a session and the good line is parsed.
        s = self.by_id["sess-corrupt"]
        self.assertEqual(s.input_tokens, 300)
        self.assertTrue(any("corrupt" in w.type.value or "corrupta" in w.message.lower()
                            for w in s.warnings))

    def test_no_file_failures(self):
        self.assertEqual(self.failed, 0)


class CostEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pricing = PricingTable.load(today="2026-06-18")
        cls.sessions, _, _ = scanner.scan(
            Config(read_paths=[CLAUDE], output_dir="/tmp/ai-usage-dashboard")
        )
        apply_costs(cls.sessions, cls.pricing)
        cls.by_id = sessions_by_id(cls.sessions)

    def test_calculated_cost_numbers(self):
        s = self.by_id["sess-valid"]
        self.assertEqual(s.cost.status, CostStatus.CALCULATED)
        # 2000 input * $15/Mtok = 0.03 ; 500 output * $75/Mtok = 0.0375
        self.assertAlmostEqual(s.cost.input_cost, 0.03, places=6)
        self.assertAlmostEqual(s.cost.output_cost, 0.0375, places=6)
        self.assertAlmostEqual(s.cost.total_cost, 0.0675, places=6)

    def test_tokens_missing_status(self):
        self.assertEqual(self.by_id["sess-notok"].cost.status, CostStatus.TOKENS_MISSING)

    def test_price_not_configured_status(self):
        self.assertEqual(
            self.by_id["sess-unknownprice"].cost.status, CostStatus.PRICE_NOT_CONFIGURED
        )

    def test_unknown_model_status(self):
        self.assertEqual(self.by_id["sess-nomodel"].cost.status, CostStatus.UNKNOWN_MODEL)

    def test_incomplete_session_never_shows_cost(self):
        for sid in ("sess-notok", "sess-unknownprice", "sess-nomodel"):
            c = self.by_id[sid].cost
            self.assertIsNone(c.total_cost)
            self.assertNotEqual(c.status, CostStatus.CALCULATED)


class AggregateTests(unittest.TestCase):
    def test_aggregates_exclude_non_calculable(self):
        pricing = PricingTable.load(today="2026-06-18")
        sessions, _, _ = scanner.scan(
            Config(read_paths=[CLAUDE], output_dir="/tmp/ai-usage-dashboard")
        )
        apply_costs(sessions, pricing)
        agg = aggregate(sessions)
        # Only sess-valid and sess-corrupt are calculable.
        self.assertAlmostEqual(agg["total_calculated_cost"], 0.0675 + _haiku_cost(), places=6)
        self.assertGreaterEqual(agg["sessions_non_calculable"], 3)


def _haiku_cost():
    # sess-corrupt: 300 in * $1/Mtok + 80 out * $5/Mtok
    return 300 * 1.0 / 1_000_000 + 80 * 5.0 / 1_000_000


class PricingStalenessTests(unittest.TestCase):
    def test_stale_price_warns(self):
        pricing = PricingTable.load(today="2030-01-01")  # far future -> stale
        mp = pricing.lookup("claude-opus-4-8")
        self.assertIsNotNone(pricing.staleness_warning(mp))

    def test_fresh_price_no_warning(self):
        pricing = PricingTable.load(today="2026-06-18")
        mp = pricing.lookup("claude-opus-4-8")
        self.assertIsNone(pricing.staleness_warning(mp))


class WritePolicyTests(unittest.TestCase):
    def test_write_into_source_path_rejected(self):
        with tempfile.TemporaryDirectory() as out:
            cfg = make_config(out)
            with self.assertRaises(PermissionError):
                cfg.assert_write_allowed(Path.home() / ".claude" / "evil.json")

    def test_output_dir_inside_source_rejected_at_construction(self):
        with self.assertRaises(ValueError):
            Config(output_dir=str(Path.home() / ".claude" / "out"))

    def test_write_into_output_dir_allowed(self):
        with tempfile.TemporaryDirectory() as out:
            cfg = make_config(out)
            resolved = cfg.assert_write_allowed(Path("report.json"))
            self.assertTrue(str(resolved).startswith(str(Path(out).resolve())))


class OfflineTests(unittest.TestCase):
    def test_socket_connect_blocked(self):
        with network_disabled(True):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                with self.assertRaises(NetworkAccessError):
                    s.connect(("example.com", 80))
            finally:
                s.close()

    def test_getaddrinfo_blocked(self):
        with network_disabled(True):
            with self.assertRaises(NetworkAccessError):
                socket.getaddrinfo("example.com", 80)

    def test_network_restored_after_context(self):
        with network_disabled(True):
            pass
        # Should not raise now (creating a socket object, not connecting).
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.close()


class IntegrityAndEndToEndTests(unittest.TestCase):
    def test_sources_unchanged_after_scan(self):
        before = verify.snapshot([CLAUDE])
        with tempfile.TemporaryDirectory() as out:
            cfg = make_config(out)
            report = run_scan(cfg, pricing=PricingTable.load(today="2026-06-18"),
                              generated_at="2026-06-18T00:00:00Z")
        after = verify.snapshot([CLAUDE])
        self.assertEqual(before, after)
        self.assertTrue(report.integrity["unchanged"])

    def test_report_written_only_to_output_dir(self):
        with tempfile.TemporaryDirectory() as out:
            cfg = make_config(out)
            report = run_scan(cfg, pricing=PricingTable.load(today="2026-06-18"),
                              generated_at="2026-06-18T00:00:00Z")
            path = write_report(report, cfg)
            self.assertTrue(str(path).startswith(str(Path(out).resolve())))
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertIn("disclaimer", data)
            self.assertIn("no representan facturación real", data["disclaimer"])

    def test_kpi_95_percent_processed(self):
        # All 5 fixture files are readable; none should block the run.
        sessions, _, failed = scanner.scan(
            Config(read_paths=[CLAUDE], output_dir="/tmp/ai-usage-dashboard")
        )
        total_files = len(list(CLAUDE.rglob("*.jsonl")))
        processed = len(sessions)
        self.assertGreaterEqual(processed / total_files, 0.95)
        self.assertEqual(failed, 0)

    def test_offline_run_makes_no_network_calls(self):
        # run_scan wraps analysis in network_disabled; a successful run proves it.
        with tempfile.TemporaryDirectory() as out:
            cfg = make_config(out)
            cfg.offline = True
            report = run_scan(cfg, pricing=PricingTable.load(today="2026-06-18"),
                              generated_at="2026-06-18T00:00:00Z")
            self.assertGreater(report.sessions_processed, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
