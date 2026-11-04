#!/usr/bin/env python3
"""Audit an explicitly normalized CSV using exact integer minor units."""
import argparse
import csv
from datetime import date, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys

FIELDS = ("record_id", "source_id", "source_locator", "account_id", "counterparty_id",
          "occurred_at", "direction", "amount", "currency", "summary")
AMOUNT = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?")
TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})?")


def minor_units(value):
    if not isinstance(value, str) or not AMOUNT.fullmatch(value):
        raise ValueError("amount must be signed decimal text with at most two fractional digits")
    negative = value.startswith("-")
    whole, _, fraction = value.lstrip("-").partition(".")
    number = int(whole) * 100 + int(fraction.ljust(2, "0"))
    return -number if negative else number


def money(number):
    sign = "-" if number < 0 else ""
    whole, fraction = divmod(abs(number), 100)
    return f"{sign}{whole}.{fraction:02d}"


def file_identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def validate_row(row):
    if None in row or any(row.get(key) is None for key in FIELDS):
        raise ValueError("row width does not match header")
    for key in FIELDS:
        if key not in ("summary", "counterparty_id") and not row[key]:
            raise ValueError(key + " is required")
        if key != "summary" and row[key] != row[key].strip():
            raise ValueError(key + " contains unnormalized whitespace")
    if row["direction"] not in ("in", "out"):
        raise ValueError("direction must be in or out")
    if not re.fullmatch(r"[A-Z]{3}", row["currency"]):
        raise ValueError("currency must be a three-letter uppercase label")
    if not TIMESTAMP.fullmatch(row["occurred_at"]):
        raise ValueError("occurred_at must be an ISO datetime including seconds")
    occurred = datetime.fromisoformat(row["occurred_at"].replace("Z", "+00:00"))
    return occurred.date(), minor_units(row["amount"])


def audit(path, accounts=None, counterparties=None, start=None, end=None):
    groups, selected, errors = {}, [], []
    ids, locations = set(), set()
    total, error_count = 0, 0

    def error(line, message):
        nonlocal error_count
        error_count += 1
        if len(errors) < 100:
            errors.append({"normalized_csv_line_end": line, "message": message})

    with path.open("rb") as raw:
        before = os.fstat(raw.fileno())
        digest = hashlib.sha256()
        for chunk in iter(lambda: raw.read(1024 * 1024), b""):
            digest.update(chunk)
        raw.seek(0)
        stream = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        if len(header) != len(set(header)) or any(k not in header for k in FIELDS):
            raise ValueError("missing or duplicate CSV header fields")
        for row in reader:
            total += 1
            try:
                day, amount = validate_row(row)
                rid = row["record_id"]
                location = (row["source_id"], row["source_locator"])
                if rid in ids:
                    raise ValueError("duplicate record_id")
                if location in locations:
                    raise ValueError("duplicate source_id + source_locator")
                ids.add(rid)
                locations.add(location)
                if accounts and row["account_id"] not in accounts:
                    continue
                if counterparties and row["counterparty_id"] not in counterparties:
                    continue
                if (start and day < start) or (end and day > end):
                    continue
                key = (row["account_id"], row["currency"])
                group = groups.setdefault(key, {
                    "account_id": key[0], "currency": key[1], "record_count": 0,
                    "in_positive_count": 0, "in_negative_count": 0, "in_zero_count": 0,
                    "out_positive_count": 0, "out_negative_count": 0, "out_zero_count": 0,
                    "in_positive_total": 0, "in_negative_total": 0, "in_signed_total": 0,
                    "out_positive_total": 0, "out_negative_total": 0, "out_signed_total": 0,
                    "first_record_date": day.isoformat(), "last_record_date": day.isoformat(),
                    "unknown_counterparty_count": 0,
                })
                direction = row["direction"]
                kind = "positive" if amount > 0 else "negative" if amount < 0 else "zero"
                group["record_count"] += 1
                group[direction + "_" + kind + "_count"] += 1
                group[direction + "_signed_total"] += amount
                if amount:
                    group[direction + "_" + kind + "_total"] += amount
                if not row["counterparty_id"]:
                    group["unknown_counterparty_count"] += 1
                group["first_record_date"] = min(group["first_record_date"], day.isoformat())
                group["last_record_date"] = max(group["last_record_date"], day.isoformat())
                selected.append({**{k: row[k] for k in FIELDS}, "normalized_csv_line_end": reader.line_num})
            except ValueError as exc:
                error(reader.line_num, str(exc))
        after = os.fstat(raw.fileno())
        if not (file_identity(before) == file_identity(after) == file_identity(path.stat())):
            raise ValueError("input changed during read")
    if not selected and not error_count:
        error(0, "no matching records; check input and scope")
    result_groups = []
    for key in sorted(groups):
        group = groups[key]
        group["signed_net_inflow"] = group["in_signed_total"] - group["out_signed_total"]
        for field in list(group):
            if field.endswith("_total") or field == "signed_net_inflow":
                group[field] = money(group[field])
        result_groups.append(group)
    return {
        "schema_version": 1, "amount_scale": 2, "input_sha256": digest.hexdigest(),
        "scope": {"accounts": sorted(accounts or []), "counterparties": sorted(counterparties or []),
                  "start_inclusive": start.isoformat() if start else None,
                  "end_inclusive": end.isoformat() if end else None,
                  "empty_filter_means": "all identifiers present in this input; not proof of full account coverage"},
        "input_record_count": total, "selected_record_count": len(selected),
        "unselected_record_count": total - len(selected) if not error_count else None,
        "errors": errors, "error_count": error_count, "errors_truncated": error_count > len(errors),
        "groups": result_groups if not error_count else None,
        "selected_records": selected if not error_count else None,
        "limits": "record arithmetic only; no balance, event deduplication, identity, source attribution, profit or loss determination",
    }


def write_new(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--account", action="append")
    parser.add_argument("--counterparty", action="append")
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.start and args.end and args.start > args.end:
            raise ValueError("start must not be after end")
        result = audit(args.input, set(args.account or []), set(args.counterparty or []), args.start, args.end)
        write_new(args.output, result)
        print(json.dumps({"input_record_count": result["input_record_count"],
                          "selected_record_count": result["selected_record_count"],
                          "error_count": result["error_count"]}))
        return 2 if result["error_count"] else 0
    except (OSError, ValueError, csv.Error) as exc:
        print("ledger audit error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
