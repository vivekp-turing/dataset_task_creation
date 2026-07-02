#!/usr/bin/env python3
"""Validate task.toml taxonomy fields against docs/alibaba/taxonomy_v1.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("pip install pyyaml", file=sys.stderr)
    sys.exit(2)


def load_taxonomy(root: Path) -> dict:
    path = root / "docs/alibaba/taxonomy_v1.yaml"
    return yaml.safe_load(path.read_text())


def parse_toml_simple(text: str) -> dict:
    """Minimal TOML parser for [metadata] fields we care about."""
    meta: dict[str, str] = {}
    in_metadata = False
    for line in text.splitlines():
        line = line.strip()
        if line == "[metadata]":
            in_metadata = True
            continue
        if line.startswith("[") and line != "[metadata]":
            in_metadata = False
        if in_metadata and "=" in line:
            key, _, val = line.partition("=")
            meta[key.strip()] = val.strip().strip('"')
    return meta


def normalize_code_lang(lang: str, tax: dict) -> str:
    aliases = tax.get("code_lang_aliases", {})
    return aliases.get(lang, lang)


def normalize_application(domain: str, tax: dict) -> str:
    aliases = tax.get("application_aliases", {})
    return aliases.get(domain, domain)


def validate_task_toml(toml_path: Path, tax: dict) -> list[str]:
    errors: list[str] = []
    meta = parse_toml_simple(toml_path.read_text())

    lang = normalize_code_lang(meta.get("language", ""), tax)
    task_type = meta.get("task_type", "")
    domain = normalize_application(meta.get("domain", ""), tax)

    all_langs = set(tax["code_lang"]["required"]) | set(tax["code_lang"]["optional"])
    if lang and lang not in all_langs:
        errors.append(f"language '{meta.get('language')}' not in taxonomy (normalized: {lang})")

    if task_type and task_type not in tax["task_type"]:
        errors.append(f"task_type '{task_type}' not in taxonomy")

    all_apps = set(tax["application"]["required"]) | set(tax["application"]["optional"])
    if domain and domain not in all_apps:
        errors.append(f"domain '{meta.get('domain')}' not in taxonomy (normalized: {domain})")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="task.toml file(s) or bundle dirs")
    parser.add_argument(
        "--root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="Repo root (default: auto-detect)",
    )
    args = parser.parse_args()
    tax = load_taxonomy(args.root)

    failed = 0
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            candidates = list(path.rglob("task.toml"))
            if not candidates:
                print(f"SKIP {path}: no task.toml")
                continue
            for c in candidates:
                errs = validate_task_toml(c, tax)
                if errs:
                    failed += 1
                    print(f"FAIL {c}")
                    for e in errs:
                        print(f"  - {e}")
                else:
                    print(f"OK   {c}")
        else:
            errs = validate_task_toml(path, tax)
            if errs:
                failed += 1
                print(f"FAIL {path}")
                for e in errs:
                    print(f"  - {e}")
            else:
                print(f"OK   {path}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
