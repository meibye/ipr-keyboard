#!/usr/bin/env python3
"""Compare BLE capture output locally using Danish keyboard rendered expectations."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path


DEAD_KEY_DISPLAY = {
    "\u0301": "´",
    "\u0300": "`",
    "\u0302": "^",
    "\u0308": "¨",
    "\u0303": "~",
}

SUPPORTED_COMPOSITIONS = {
    "\u0301": set("aeiouyAEIOUY"),
    "\u0300": set("aeiouAEIOU"),
    "\u0302": set("aeiouAEIOU"),
    "\u0308": set("aeiouyAEIOU"),
    "\u0303": set("anoANO"),
}
DIRECT_RENDERED_CHARACTERS = {"–", "—", "Ÿ"}


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def iter_clusters(text: str):
    cluster = ""
    for ch in text:
        if cluster and unicodedata.combining(ch):
            cluster += ch
            continue
        if cluster:
            yield cluster
        cluster = ch
    if cluster:
        yield cluster


def supports_dead_key_composition(base: str, mark: str) -> bool:
    return base in SUPPORTED_COMPOSITIONS.get(mark, set())


def split_explicit_cluster(element: str):
    if len(element) < 2 or not unicodedata.combining(element[-1]):
        return None
    return element[:-1], element[-1]


def render_text_element(element: str) -> str:
    if element in DIRECT_RENDERED_CHARACTERS:
        return element

    explicit = split_explicit_cluster(element)
    if explicit is not None:
        base, mark = explicit
        dead = DEAD_KEY_DISPLAY.get(mark)
        if dead is not None:
            recomposed = unicodedata.normalize("NFC", element)
            if supports_dead_key_composition(base, mark) and len(recomposed) == 1:
                return recomposed
            return f"{dead}{base}"

    decomposed = unicodedata.normalize("NFD", element)
    if len(decomposed) == 2:
        base, mark = decomposed[0], decomposed[1]
        dead = DEAD_KEY_DISPLAY.get(mark)
        if dead is not None:
            recomposed = unicodedata.normalize("NFC", decomposed)
            if supports_dead_key_composition(base, mark) and len(recomposed) == 1:
                return recomposed
            return f"{dead}{base}"

    return element


def convert_to_keyboard_rendered_text(text: str) -> str:
    return "".join(render_text_element(element) for element in iter_clusters(text))


def context_at(text: str, index: int, radius: int = 20) -> str:
    if not text:
        return ""
    start = max(0, index - radius)
    end = min(len(text), index + radius + 1)
    return text[start:end].replace("\n", "<LF>")


def build_report(expected_source: str, expected: str, captured: str) -> tuple[dict, list[str]]:
    max_len = min(len(expected), len(captured))
    first_mismatch = -1
    for i in range(max_len):
        if expected[i] != captured[i]:
            first_mismatch = i
            break
    if first_mismatch == -1 and len(expected) != len(captured):
        first_mismatch = max_len

    expected_lines = expected.split("\n")
    captured_lines = captured.split("\n")
    max_lines = max(len(expected_lines), len(captured_lines))
    line_diffs: list[str] = []
    for line in range(max_lines):
        expected_line = expected_lines[line] if line < len(expected_lines) else "<MISSING>"
        captured_line = captured_lines[line] if line < len(captured_lines) else "<MISSING>"
        if expected_line != captured_line:
            line_diffs.append(f"Line {line + 1}")
            line_diffs.append(f"  expected: {expected_line}")
            line_diffs.append(f"  captured: {captured_line}")

    match = expected == captured
    report_lines = [
        f"Match: {match}",
        f"Expected source length: {len(expected_source)}",
        f"Expected rendered length: {len(expected)}",
        f"Captured length: {len(captured)}",
        f"First mismatch index: {first_mismatch}",
    ]

    if first_mismatch >= 0:
        expected_char = ord(expected[first_mismatch]) if first_mismatch < len(expected) else None
        captured_char = ord(captured[first_mismatch]) if first_mismatch < len(captured) else None
        report_lines.extend(
            [
                f"Expected char code at mismatch: {expected_char}",
                f"Captured char code at mismatch: {captured_char}",
                f"Expected context: {context_at(expected, first_mismatch)}",
                f"Captured context: {context_at(captured, first_mismatch)}",
            ]
        )

    report_lines.append("")
    report_lines.append("Line-by-line differences:")
    if line_diffs:
        report_lines.extend(line_diffs)
    else:
        report_lines.append("  none")

    result = {
        "match": match,
        "expected_source_length": len(expected_source),
        "expected_rendered_length": len(expected),
        "captured_length": len(captured),
        "first_mismatch_index": first_mismatch,
    }
    return result, report_lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", required=True, help="Path to source fixture text.")
    parser.add_argument("--captured", required=True, help="Path to locally copied capture text.")
    parser.add_argument("--report", required=True, help="Path to write the diff report.")
    parser.add_argument(
        "--mode",
        choices=("exact", "rendered"),
        default="rendered",
        help="Compare exact source text or Danish-keyboard rendered expectation.",
    )
    args = parser.parse_args()

    expected_path = Path(args.expected)
    captured_path = Path(args.captured)
    report_path = Path(args.report)

    expected_source = normalize_text(expected_path.read_text(encoding="utf-8"))
    captured = normalize_text(captured_path.read_text(encoding="utf-8"))
    if args.mode == "rendered":
        expected = convert_to_keyboard_rendered_text(expected_source)
    else:
        expected = expected_source

    result, report_lines = build_report(expected_source, expected, captured)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({**result, "report_path": str(report_path)}, ensure_ascii=False))
    return 0 if result["match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
