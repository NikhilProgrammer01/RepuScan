"""Load `Dataset.xlsx` into normalized dicts using only the Python stdlib.

An .xlsx file is just a ZIP of XML parts. We read two of them:
- `xl/sharedStrings.xml` — a string pool; text cells store an *index* into it.
- `xl/worksheets/sheet1.xml` — the grid; each `<c>` cell has a column ref (e.g. "C7"),
  an optional type `t`, and a `<v>` value.

This avoids pandas/openpyxl entirely (per the plan's "stdlib only" constraint), keeping
`requirements.txt` tiny and the dependency surface auditable.

We deliberately do **no** cleaning here — values come out raw (Excel serial dates stay
ints, mojibake stays as-is). `clean.py` owns standardization. `load.py`'s only job is a
faithful row→dict mapping plus a quick load report.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

from config import DATASET_PATH

# Worksheet XML uses the SpreadsheetML namespace on every tag. Rather than carry
# the prefix around, we strip namespaces as we iterate (see `_localname`).
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Map the dataset's header labels → the normalized dict keys the rest of the
# pipeline uses. Matching is case/space-insensitive (see `_normalize_header`).
_HEADER_TO_KEY: dict[str, str] = {
    "date": "date_serial",
    "url": "url",
    "source name": "source_name",
    "title": "title",
    "opening text": "opening_text",
    "hit sentence": "hit_sentence",
    "driver": "driver",
    "sub driver": "sub_driver",
    "sentiment": "sentiment",
    "reach": "reach",
}

# Order of fields in every emitted row dict (header keys first, then our metadata).
ROW_KEYS: tuple[str, ...] = (
    "date_serial",
    "url",
    "source_name",
    "title",
    "opening_text",
    "hit_sentence",
    "driver",
    "sub_driver",
    "sentiment",
    "reach",
)

_CELL_REF_RE = re.compile(r"^([A-Z]+)\d+$")


@dataclass
class LoadReport:
    """Quick summary of what `load_dataset` saw — printed by `run.py`."""

    total_rows: int = 0
    headers: list[str] = field(default_factory=list)
    blank_source: int = 0
    blank_reach: int = 0
    blank_url: int = 0

    def summary(self) -> str:
        return (
            f"Loaded {self.total_rows} rows | "
            f"blank source: {self.blank_source} | "
            f"blank reach: {self.blank_reach} | "
            f"blank url: {self.blank_url}"
        )


def _localname(tag: str) -> str:
    """Strip the `{namespace}` prefix from an ElementTree tag."""
    return tag.rsplit("}", 1)[-1]


def _col_letters(cell_ref: str) -> str:
    """'C7' -> 'C'. Returns '' if the ref is malformed."""
    m = _CELL_REF_RE.match(cell_ref)
    return m.group(1) if m else ""


def _normalize_header(text: str) -> str:
    """Collapse whitespace + lowercase so 'Sub driver' / 'Sub  Driver' both match."""
    return " ".join(text.split()).lower()


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    """Return the shared-string pool as a list indexed by string id.

    Each `<si>` may hold a single `<t>` or several `<r><t>` rich-text runs; we
    concatenate all descendant `<t>` text so either layout yields the full string.
    """
    try:
        raw = zf.read("xl/sharedStrings.xml")
    except KeyError:  # a workbook with zero string cells has no shared strings part
        return []

    strings: list[str] = []
    root = ET.fromstring(raw)
    for si in root:
        if _localname(si.tag) != "si":
            continue
        parts = [
            node.text or ""
            for node in si.iter()
            if _localname(node.tag) == "t"
        ]
        strings.append("".join(parts))
    return strings


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    """Resolve a `<c>` cell to its text value (raw, untrimmed)."""
    cell_type = cell.get("t")

    if cell_type == "inlineStr":  # value lives in <is><t>...</t></is>
        return "".join(
            node.text or ""
            for node in cell.iter()
            if _localname(node.tag) == "t"
        )

    v = next((c for c in cell if _localname(c.tag) == "v"), None)
    if v is None or v.text is None:
        return ""

    if cell_type == "s":  # shared-string index
        try:
            return shared[int(v.text)]
        except (ValueError, IndexError):
            return ""
    # numeric, boolean, or inline formula string ("str") — take the raw value.
    return v.text


def load_dataset(path: Path | None = None) -> tuple[list[dict[str, str]], LoadReport]:
    """Parse the workbook's first sheet into normalized row dicts.

    Returns `(rows, report)`. Each row dict has every key in `ROW_KEYS` (missing
    cells become ""). The header row is consumed to map columns; if the file's
    headers don't match the expected layout we fall back to column order A..J.
    """
    path = path or DATASET_PATH
    report = LoadReport()

    with zipfile.ZipFile(path) as zf:
        shared = _read_shared_strings(zf)
        sheet_xml = zf.read("xl/worksheets/sheet1.xml")

    root = ET.fromstring(sheet_xml)
    sheet_data = next(
        (el for el in root if _localname(el.tag) == "sheetData"), None
    )
    if sheet_data is None:
        return [], report

    rows = list(sheet_data)
    if not rows:
        return [], report

    # --- Header row → column-letter → normalized key map -------------------
    header_cells = {
        _col_letters(c.get("r", "")): _cell_text(c, shared)
        for c in rows[0]
        if _localname(c.tag) == "c"
    }
    report.headers = [header_cells[k] for k in sorted(header_cells)]

    col_to_key: dict[str, str] = {}
    for letter, label in header_cells.items():
        key = _HEADER_TO_KEY.get(_normalize_header(label))
        if key:
            col_to_key[letter] = key

    # Fallback: if headers didn't map cleanly, assume the documented A..J order.
    if len(col_to_key) < len(_HEADER_TO_KEY):
        col_to_key = dict(zip("ABCDEFGHIJ", ROW_KEYS))

    # --- Data rows ---------------------------------------------------------
    out: list[dict[str, str]] = []
    for row in rows[1:]:
        if _localname(row.tag) != "row":
            continue
        record = {k: "" for k in ROW_KEYS}
        for cell in row:
            if _localname(cell.tag) != "c":
                continue
            key = col_to_key.get(_col_letters(cell.get("r", "")))
            if key:
                record[key] = _cell_text(cell, shared).strip()

        # Skip fully empty rows (Excel sometimes pads the used range).
        if not any(record.values()):
            continue

        out.append(record)
        if not record["source_name"]:
            report.blank_source += 1
        if not record["reach"]:
            report.blank_reach += 1
        if not record["url"]:
            report.blank_url += 1

    report.total_rows = len(out)
    return out, report


if __name__ == "__main__":  # quick manual check: `python pipeline/load.py`
    records, rep = load_dataset()
    print(rep.summary())
    print("Headers:", rep.headers)
    if records:
        print("\nFirst row:")
        for k, val in records[0].items():
            preview = val if len(val) <= 80 else val[:77] + "..."
            print(f"  {k:14} = {preview!r}")
