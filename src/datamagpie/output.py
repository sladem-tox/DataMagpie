"""Output serialization shared by data sources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def write_dataframe(frame: Any, output: Path) -> None:
    """Write a pandas DataFrame to CSV or JSON based on its suffix."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".csv":
        frame.to_csv(output, index=False)
    elif output.suffix.lower() == ".tsv":
        frame.to_csv(output, sep="\t", index=False)
    elif output.suffix.lower() == ".json":
        frame.to_json(output, orient="records", indent=2)
    else:
        raise ValueError("output must use a .csv, .tsv, or .json extension")


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def write_records(records: Iterable[dict[str, Any]], output: Path | None) -> None:
    rows = list(records)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
    if output and output.suffix.lower() == ".csv":
        import pandas as pd

        pd.DataFrame(rows).to_csv(output, index=False)
        return

    payload = json.dumps(rows, indent=2, default=_json_default)
    if output:
        output.write_text(payload + "\n", encoding="utf-8")
