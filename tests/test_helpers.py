import csv
from datetime import date
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/police-fund-forensics/scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger = load("audit_ledger")
manifest = load("evidence_manifest")


def row(index, **changes):
    value = dict(zip(ledger.FIELDS, ["SYN-R" + str(index), "SYN-F1", "Sheet1!" + str(index + 1),
                                  "SYN-A", "SYN-B", "2025-01-05T10:00:00", "out", "1.00", "CNY", "synthetic"]))
    value.update(changes)
    return value


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.csv"

    def write(self, rows, fields=ledger.FIELDS):
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_exact_minor_units_and_large_amounts(self):
        self.write([row(1, amount="0.10"), row(2, amount="0.20"), row(3, amount="1234567890123456789012345.67")])
        result = ledger.audit(self.path)
        self.assertEqual(result["groups"][0]["out_signed_total"], "1234567890123456789012345.97")

    def test_negative_reversal_is_not_absolute_value(self):
        self.write([row(1, amount="100"), row(2, amount="-100.00"), row(3, amount="100.00"), row(4, amount="0")])
        group = ledger.audit(self.path)["groups"][0]
        self.assertEqual(group["out_positive_count"], 2)
        self.assertEqual(group["out_negative_count"], 1)
        self.assertEqual(group["out_zero_count"], 1)
        self.assertEqual(group["out_positive_total"], "200.00")
        self.assertEqual(group["out_negative_total"], "-100.00")
        self.assertEqual(group["out_signed_total"], "100.00")
        self.assertEqual(group["signed_net_inflow"], "-100.00")

    def test_scope_does_not_drop_non_keyword_payment(self):
        result = ledger.audit(ROOT / "evals/fixtures/ledger.csv", {"SYN-CORP-A"}, {"SYN-CARD-X"}, date(2025, 1, 1), date(2025, 1, 31))
        self.assertEqual(result["selected_record_count"], 4)
        self.assertEqual(result["groups"][0]["out_signed_total"], "3400.00")
        subset = [x for x in result["selected_records"] if "充值" in x["summary"]]
        self.assertEqual(len(subset), 3)
        self.assertEqual(sum(ledger.minor_units(x["amount"]) for x in subset), 320000)

    def test_currency_and_mirror_accounts_stay_separate(self):
        self.write([row(1, amount="1000.00"), row(2, account_id="SYN-B", counterparty_id="SYN-A", direction="in", amount="1000.00"), row(3, currency="USD", amount="1.00")])
        result = ledger.audit(self.path)
        self.assertEqual(len(result["groups"]), 3)
        self.assertNotIn("grand_total", result)

    def test_duplicate_record_fails_closed(self):
        self.write([row(1), row(2, record_id="SYN-R1")])
        result = ledger.audit(self.path)
        self.assertEqual(result["error_count"], 1)
        self.assertIsNone(result["groups"])
        self.assertIsNone(result["selected_records"])

    def test_duplicate_source_locator_fails_closed(self):
        self.write([row(1), row(2, source_locator="Sheet1!2")])
        result = ledger.audit(self.path)
        self.assertEqual(result["error_count"], 1)
        self.assertIsNone(result["groups"])

    def test_invalid_values_never_yield_partial_totals(self):
        for change in [{"amount": "NaN"}, {"amount": "1e3"}, {"amount": "1.001"},
                       {"amount": "1,000.00"}, {"amount": "+1"}, {"amount": " 1.00"},
                       {"direction": "debit"}, {"occurred_at": "2025-02-30T10:00:00"},
                       {"occurred_at": "2025-01-01"}, {"account_id": " SYN-A"},
                       {"currency": "cny"}, {"source_locator": ""}]:
            with self.subTest(change=change):
                self.write([row(1), row(2, **change)])
                result = ledger.audit(self.path)
                self.assertEqual(result["error_count"], 1)
                self.assertIsNone(result["groups"])

    def test_bad_row_outside_filter_still_fails(self):
        self.write([row(1), row(2, account_id="SYN-OTHER", amount="bad")])
        result = ledger.audit(self.path, {"SYN-A"})
        self.assertEqual(result["error_count"], 1)
        self.assertIsNone(result["groups"])

    def test_inclusive_date_boundaries_and_explicit_scope(self):
        self.write([row(1, occurred_at="2025-01-01T00:00:00Z"),
                    row(2, occurred_at="2025-01-31T23:59:59+08:00"),
                    row(3, occurred_at="2025-02-01T00:00:00")])
        result = ledger.audit(self.path, start=date(2025, 1, 1), end=date(2025, 1, 31))
        self.assertEqual(result["selected_record_count"], 2)
        self.assertEqual(result["unselected_record_count"], 1)
        self.assertEqual(result["groups"][0]["last_record_date"], "2025-01-31")

    def test_no_match_is_not_proof_of_no_transactions(self):
        self.write([row(1)])
        result = ledger.audit(self.path, {"SYN-UNKNOWN"})
        self.assertEqual(result["error_count"], 1)
        self.assertIsNone(result["groups"])

    def test_unknown_counterparty_and_original_summary_retained(self):
        self.write([row(1, counterparty_id="", summary="原摘要\n第二行")])
        result = ledger.audit(self.path)
        self.assertEqual(result["groups"][0]["unknown_counterparty_count"], 1)
        self.assertEqual(result["selected_records"][0]["summary"], "原摘要\n第二行")

    def test_missing_and_duplicate_headers_rejected(self):
        self.path.write_text("record_id,record_id\nA,A\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            ledger.audit(self.path)

    def test_cli_error_exit_and_source_preservation(self):
        self.write([row(1), row(2, amount="bad")])
        before = self.path.read_bytes()
        output = self.path.parent / "audit.json"
        result = subprocess.run([sys.executable, str(SCRIPTS / "audit_ledger.py"), str(self.path), "--output", str(output)], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(json.loads(output.read_text())["groups"])
        self.assertEqual(self.path.read_bytes(), before)

    def test_cli_refuses_overwrite(self):
        self.write([row(1)])
        output = self.path.parent / "result.json"
        output.write_text("protected", encoding="utf-8")
        result = subprocess.run([sys.executable, str(SCRIPTS / "audit_ledger.py"), str(self.path), "--output", str(output)], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(), "protected")


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "materials"
        self.root.mkdir()
        (self.root / "原始.csv").write_bytes(b"synthetic\n")
        self.output = self.base / "manifest.json"

    def command(self, *arguments):
        return subprocess.run([sys.executable, str(SCRIPTS / "evidence_manifest.py"), *arguments], capture_output=True, text=True)

    def test_create_verify_and_source_unchanged(self):
        before = (self.root / "原始.csv").read_bytes()
        self.assertEqual(self.command("create", "--root", str(self.root), "--output", str(self.output)).returncode, 0)
        value = json.loads(self.output.read_text())
        self.assertEqual(value["files"][0]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(self.command("verify", "--root", str(self.root), "--manifest", str(self.output)).returncode, 0)
        self.assertEqual((self.root / "原始.csv").read_bytes(), before)

    def test_detect_changed_missing_and_unexpected(self):
        (self.root / "missing.csv").write_text("x")
        self.command("create", "--root", str(self.root), "--output", str(self.output))
        (self.root / "原始.csv").write_bytes(b"synthetic changed\n")
        (self.root / "missing.csv").unlink()
        (self.root / "new.csv").write_text("new")
        result = self.command("verify", "--root", str(self.root), "--manifest", str(self.output))
        self.assertEqual(result.returncode, 1)
        value = json.loads(result.stdout)
        self.assertEqual(value["changed"], ["原始.csv"])
        self.assertEqual(value["missing"], ["missing.csv"])
        self.assertEqual(value["unexpected"], ["new.csv"])

    def test_reject_manifest_inside_materials(self):
        result = self.command("create", "--root", str(self.root), "--output", str(self.root / "manifest.json"))
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / "manifest.json").exists())

    def test_non_ascii_paths_work_with_ascii_console(self):
        self.command("create", "--root", str(self.root), "--output", str(self.output))
        (self.root / "原始.csv").write_text("changed")
        env = {**os.environ, "PYTHONIOENCODING": "ascii"}
        result = subprocess.run([sys.executable, str(SCRIPTS / "evidence_manifest.py"),
                                 "verify", "--root", str(self.root), "--manifest", str(self.output)],
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)["changed"], ["原始.csv"])

    def test_refuse_existing_output(self):
        self.output.write_text("protected")
        self.assertEqual(self.command("create", "--root", str(self.root), "--output", str(self.output)).returncode, 2)
        self.assertEqual(self.output.read_text(), "protected")

    def test_reject_symlink(self):
        try:
            (self.root / "link").symlink_to(self.root / "原始.csv")
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        self.assertEqual(self.command("create", "--root", str(self.root), "--output", str(self.output)).returncode, 2)
        self.assertFalse(self.output.exists())

    def test_manifest_structure_and_traversal_rejected(self):
        for path in ["../outside", "/absolute", "a/../outside", "a//b", "C:/outside", "a\\b", "."]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                manifest.validate_manifest({"schema_version": 1, "algorithm": "sha256", "files": [{"path": path, "bytes": 1, "sha256": "a" * 64}]})
        entry = {"path": "a", "bytes": 1, "sha256": "a" * 64}
        with self.assertRaises(ValueError):
            manifest.validate_manifest({"schema_version": 1, "algorithm": "sha256", "files": [entry, entry]})


if __name__ == "__main__":
    unittest.main()
