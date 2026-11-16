"""Parse HKUST academic calendar PDFs (Registry) into term / exam / holiday tables.

Source: https://registry.hkust.edu.hk/academic-calendar -> calendar_dates/dates<YY>-<YY>confirmed.pdf
Run: .venv/bin/python parse_hkust_calendar.py  (PDFs expected in ./hkust_calendar/)
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        start=1,
    )
}

# event text (as printed) -> logical key
TERM_EVENTS = {
    "Fall Term commences": ("fall", "start"),
    "Last day of Fall Term classes": ("fall", "classes_end"),
    "Fall Term Examinations": ("fall", "exam"),
    "Last day of Fall Term": ("fall", "end"),
    "Spring Term commences": ("spring", "start"),
    "Last day of Spring Term classes": ("spring", "classes_end"),
    "Spring Term Examinations": ("spring", "exam"),
    "Last day of Spring Term": ("spring", "end"),
    "Summer Term commences": ("summer", "start"),
    "Last day of Summer Term classes": ("summer", "classes_end"),
    "Summer Term Examinations": ("summer", "exam"),
    "Last day of Summer Term": ("summer", "end"),
    "Winter Term commences": ("winter", "start"),
    "Last day of Winter Term": ("winter", "end"),
}

MONTH_HDR = re.compile(
    r"^\s*(" + "|".join(MONTHS) + r")\s*(?:,\s*(\d{4}))?\s*$"
)
DATE_FIELD = re.compile(r"^\s*(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*$")


def pdf_text(path: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True, capture_output=True, text=True,
    ).stdout


def parse(path: Path) -> list[dict]:
    year, month = None, None
    rows: list[dict] = []
    for line in pdf_text(path).splitlines():
        m = MONTH_HDR.match(line)
        if m:
            month = MONTHS[m.group(1)]
            if m.group(2):
                year = int(m.group(2))
            continue
        if month is None or year is None:
            continue
        for event, (term, key) in TERM_EVENTS.items():
            if event not in line:
                continue
            # the date field sits between the day grid and the event text
            head = line.split(event)[0]
            fields = [DATE_FIELD.match(c) for c in re.findall(r"\s{2,}\S[^\s]*(?:\s*-\s*\d+)?", head)]
            cands = [f for f in fields if f]
            if not cands:
                continue
            d1 = int(cands[-1].group(1))
            d2 = int(cands[-1].group(2) or d1)
            rows.append(
                {
                    "academic_year": path.stem.replace("cal_", "").replace("-", "-"),
                    "term": term,
                    "event": key,
                    "start": f"{year:04d}-{month:02d}-{d1:02d}",
                    "end": f"{year:04d}-{month:02d}-{d2:02d}",
                }
            )
            break
    return rows


def main() -> None:
    src = Path(__file__).parent / "hkust_calendar"
    out = {}
    for pdf in sorted(src.glob("cal_*.pdf")):
        for r in parse(pdf):
            ay = pdf.stem.replace("cal_", "")
            out.setdefault(ay, {}).setdefault(r["term"], {})[r["event"]] = (
                r["start"] if r["start"] == r["end"] else [r["start"], r["end"]]
            )
    dest = Path(__file__).parent / "hkust_calendar_terms.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for ay, terms in out.items():
        print(ay, json.dumps(terms, ensure_ascii=False))


if __name__ == "__main__":
    main()
