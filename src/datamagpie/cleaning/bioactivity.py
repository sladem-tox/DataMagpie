"""Cleaning and labeling for comparable ChEMBL bioactivity records."""

from __future__ import annotations

import math
from typing import Sequence

import pandas as pd

DEFAULT_STANDARD_TYPE = "IC50"
VALID_ACTIVITY_UNITS = ("nM",)
DEFAULT_ACTIVITY_BINS = (0, 1_000, 10_000, 1_000_000)
DEFAULT_ACTIVITY_LABELS = ("active", "intermediate", "inactive")


def _validate_bins(bins: Sequence[float], labels: Sequence[str]) -> None:
    if len(bins) != len(labels) + 1:
        raise ValueError("activity bins must contain exactly one more value than labels")
    if any(left >= right for left, right in zip(bins, bins[1:])):
        raise ValueError("activity bins must be strictly increasing")


def clean_bioactivity_data(
    frame: pd.DataFrame,
    *,
    standard_type: str = DEFAULT_STANDARD_TYPE,
    valid_units: Sequence[str] = VALID_ACTIVITY_UNITS,
    activity_bins: Sequence[float] = DEFAULT_ACTIVITY_BINS,
    activity_labels: Sequence[str] = DEFAULT_ACTIVITY_LABELS,
) -> pd.DataFrame:
    """Clean raw records, classify activity, deduplicate compounds, and add pIC50."""
    required = {"molecule_chembl_id", "canonical_smiles", "standard_value", "standard_units"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"input is missing required columns: {', '.join(missing)}")
    _validate_bins(activity_bins, activity_labels)

    cleaned = frame.dropna(subset=["standard_value"]).copy()
    if "standard_type" in cleaned.columns:
        cleaned = cleaned[cleaned["standard_type"].eq(standard_type)]
    cleaned = cleaned[cleaned["standard_units"].isin(valid_units)]
    cleaned["standard_value"] = pd.to_numeric(cleaned["standard_value"], errors="coerce")
    cleaned = cleaned.dropna(subset=["standard_value"])
    cleaned = cleaned[cleaned["standard_value"] > 0]

    cleaned["activity"] = pd.cut(
        cleaned["standard_value"],
        bins=list(activity_bins),
        labels=list(activity_labels),
        right=False,
    )
    result = cleaned[
        ["molecule_chembl_id", "canonical_smiles", "standard_value", "activity"]
    ].copy()
    result.rename(
        columns={
            "molecule_chembl_id": "ChEMBL",
            "canonical_smiles": "SMILES",
            "standard_value": f"{standard_type} nM",
        },
        inplace=True,
    )
    result.drop_duplicates(subset=["SMILES"], keep="first", inplace=True)
    result = result.loc[:, ~result.columns.duplicated()]
    result.dropna(subset=["activity"], inplace=True)
    result = add_pic50(result, value_column=f"{standard_type} nM")
    return result.reset_index(drop=True)


def add_pic50(frame: pd.DataFrame, *, value_column: str = "IC50 nM") -> pd.DataFrame:
    """Add pIC50 from a positive concentration in nM."""
    if value_column not in frame.columns:
        raise ValueError(f"input is missing required column: {value_column}")
    result = frame.copy()
    result[value_column] = pd.to_numeric(result[value_column], errors="coerce")
    result = result.dropna(subset=[value_column])
    result = result[result[value_column] > 0].copy()
    result["pIC50"] = result[value_column].map(lambda value: 9 - math.log10(value)).round(4)
    return result.reset_index(drop=True)


def pic50_to_ic50_nm(pic50: float) -> float:
    """Convert pIC50 back to IC50 in nM."""
    return float(10 ** (9 - pic50))
