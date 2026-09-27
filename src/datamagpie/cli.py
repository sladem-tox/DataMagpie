"""Command-line interface for DataMagpie."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from datamagpie.cleaning.bioactivity import (
    DEFAULT_ACTIVITY_BINS,
    DEFAULT_ACTIVITY_LABELS,
    DEFAULT_STANDARD_TYPE,
    VALID_ACTIVITY_UNITS,
    clean_bioactivity_data,
)
from datamagpie.output import write_dataframe, write_records
from datamagpie.sources.chembl import ChemblSource
from datamagpie.sources.drugcentral import DrugCentralSettings, DrugCentralSource
from datamagpie.sources.ct_ade import CtAdeSource
from datamagpie.sources.tdc import TdcSource


DATA_DIR = Path("data")


def _filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "dataset"


def _default_output(source: str, args: argparse.Namespace) -> Path:
    if source == "chembl":
        name = (
            f"chembl_bioactivity_{args.target_query}"
            if args.target_query
            else f"chembl_{args.resource}"
        )
    else:
        name = (
            f"tdc_{args.task}_{args.name}"
            if source == "tdc"
            else f"drugcentral_{args.operation}"
        )
    return DATA_DIR / f"{_filename_part(name)}.json"


def _default_clean_output(input_path: Path) -> Path:
    return DATA_DIR / f"{_filename_part(input_path.stem)}_cleaned.csv"


def _read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise ValueError(f"input file does not exist: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".json":
        return pd.read_json(path)
    raise ValueError("input must use a .csv or .json extension")


def _key_value(value: str) -> tuple[str, str]:
    key, separator, item = value.partition("=")
    if not separator or not key:
        raise argparse.ArgumentTypeError("expected KEY=VALUE")
    return key, item


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path (.json or .csv); defaults to data/<source>.json",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="datamagpie",
        description="Download data from biomedical data sources.",
    )
    commands = parser.add_subparsers(dest="source", required=True)

    chembl = commands.add_parser("chembl", help="download data from ChEMBL")
    chembl.add_argument(
        "--resource",
        default="molecule",
        help="ChEMBL resource to query, such as molecule or target",
    )
    chembl.add_argument(
        "--filter",
        dest="filters",
        action="append",
        type=_key_value,
        metavar="KEY=VALUE",
        help="resource filter; may be repeated",
    )
    chembl.add_argument(
        "--field",
        dest="fields",
        action="append",
        metavar="NAME",
        help="field to return; may be repeated",
    )
    chembl.add_argument("--limit", type=int, help="maximum number of records")
    chembl.add_argument(
        "--target-query",
        help="search ChEMBL targets and download their bioactivity records",
    )
    chembl.add_argument(
        "--standard-type",
        default="IC50",
        help="bioactivity measurement type when --target-query is used",
    )
    chembl.add_argument(
        "--unit",
        help="bioactivity unit filter when --target-query is used, e.g. nM",
    )
    chembl.add_argument(
        "--count",
        action="store_true",
        help="print the number of matching records without downloading them",
    )
    _add_output_options(chembl)

    tdc = commands.add_parser("tdc", help="download a dataset from Therapeutics Data Commons")
    tdc.add_argument(
        "--task",
        choices=("adme", "tox", "dti", "hts", "drugres"),
        default="adme",
        help="TDC task family",
    )
    tdc.add_argument("--name", required=True, help="TDC dataset name")
    _add_output_options(tdc)

    ct_ade = commands.add_parser(
        "ct-ade",
        help="download the public CT-ADE benchmark dataset",
    )
    ct_ade.add_argument(
        "--version",
        choices=("soc", "pt"),
        required=True,
        help="annotation level: SOC or PT",
    )
    ct_ade.add_argument(
        "--split",
        dest="splits",
        choices=("train", "val", "test"),
        action="append",
        help="split to download; may be repeated (default: all core splits)",
    )
    ct_ade.add_argument(
        "--include-frequencies",
        action="store_true",
        help="also download the large *_frequencies.csv files",
    )
    ct_ade.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="destination directory; defaults to data/ct-ade-<version>",
    )

    drugcentral = commands.add_parser(
        "drugcentral",
        help="query DrugCentral through the BioClients PostgreSQL API",
    )
    drugcentral.add_argument(
        "--operation",
        required=True,
        choices=sorted(DrugCentralSource._operations),
        help="DrugCentral operation to run",
    )
    drugcentral.add_argument(
        "--ids",
        nargs="+",
        help="IDs or regular-expression search terms required by the operation",
    )
    drugcentral.add_argument("--xref-type", help="xref type for get_structure_by_xref")
    drugcentral.add_argument("--dbhost", help="database host")
    drugcentral.add_argument("--dbport", help="database port")
    drugcentral.add_argument("--dbname", help="database name")
    drugcentral.add_argument("--dbuser", help="database user")
    drugcentral.add_argument("--dbpassword", help="database password")
    drugcentral.add_argument(
        "--config",
        type=Path,
        help="YAML config with DBHOST, DBPORT, DBNAME, DBUSR, and DBPW",
    )
    drugcentral.add_argument("--schema", default="public", help="database schema")
    drugcentral.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path; defaults to data/drugcentral_<operation>.tsv",
    )

    cleaning = commands.add_parser(
        "clean-bioactivity",
        help="clean and label raw bioactivity records",
    )
    cleaning.add_argument("--input", type=Path, required=True, help="raw .json or .csv file")
    cleaning.add_argument(
        "--standard-type",
        default=DEFAULT_STANDARD_TYPE,
        help=f"measurement type to retain (default: {DEFAULT_STANDARD_TYPE})",
    )
    cleaning.add_argument(
        "--unit",
        dest="units",
        action="append",
        help="valid activity unit; may be repeated (default: nM)",
    )
    cleaning.add_argument(
        "--bins",
        nargs="+",
        type=float,
        default=list(DEFAULT_ACTIVITY_BINS),
        help="activity bin edges (default: 0 1000 10000 1000000)",
    )
    cleaning.add_argument(
        "--label",
        dest="labels",
        nargs="+",
        default=list(DEFAULT_ACTIVITY_LABELS),
        help="activity labels (default: active intermediate inactive)",
    )
    cleaning.add_argument(
        "-o",
        "--output",
        type=Path,
        help="cleaned .csv or .json output; defaults to data/<input>_cleaned.csv",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.source == "clean-bioactivity":
            cleaned = clean_bioactivity_data(
                _read_table(args.input),
                standard_type=args.standard_type,
                valid_units=args.units or VALID_ACTIVITY_UNITS,
                activity_bins=args.bins,
                activity_labels=args.labels,
            )
            output = args.output or _default_clean_output(args.input)
            write_dataframe(cleaned, output)
            print(f"Wrote {len(cleaned)} cleaned records to {output}.")
            return 0
        if args.source == "ct-ade":
            output_dir = args.output_dir or DATA_DIR / f"ct-ade-{args.version}"
            files = CtAdeSource().download(
                version=args.version,
                output_dir=output_dir,
                splits=args.splits,
                include_frequencies=args.include_frequencies,
            )
            print(f"Downloaded {len(files) - 1} CT-ADE file(s) to {output_dir}.")
            print(f"Wrote manifest to {files[-1]}.")
            return 0
        if args.source == "drugcentral":
            if args.config:
                settings = DrugCentralSource.settings_from_file(args.config)
            elif all(
                value
                for value in (
                    args.dbhost,
                    args.dbport,
                    args.dbname,
                    args.dbuser,
                    args.dbpassword,
                )
            ):
                settings = DrugCentralSettings(
                    host=args.dbhost,
                    port=args.dbport,
                    database=args.dbname,
                    user=args.dbuser,
                    password=args.dbpassword,
                    schema=args.schema,
                )
            else:
                raise ValueError(
                    "provide --config or all of --dbhost, --dbport, --dbname, "
                    "--dbuser, and --dbpassword"
                )
            result = DrugCentralSource().execute(
                operation=args.operation,
                settings=settings,
                ids=args.ids,
                xref_type=args.xref_type,
            )
            output = args.output or DATA_DIR / f"drugcentral_{args.operation}.tsv"
            if isinstance(result, pd.DataFrame):
                write_dataframe(result, output)
            elif isinstance(result, dict):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(result, indent=2, default=str),
                    encoding="utf-8",
                )
            else:
                raise ValueError(
                    f"DrugCentral operation {args.operation} returned unsupported output"
                )
            print(f"Wrote DrugCentral results to {output}.")
            return 0
        if args.source == "chembl":
            source = ChemblSource()
            filters = dict(args.filters or [])
            if args.count:
                if args.target_query:
                    count = source.count_bioactivity(
                        target_query=args.target_query,
                        standard_type=args.standard_type,
                        unit=args.unit,
                    )
                    print(
                        f"Found {count} {args.standard_type} records for "
                        f"'{args.target_query}'."
                    )
                else:
                    print(
                        f"Found {source.count(resource=args.resource, filters=filters)} "
                        f"records for '{args.resource}'."
                    )
                return 0
            if args.target_query:
                records = source.fetch_bioactivity(
                    target_query=args.target_query,
                    standard_type=args.standard_type,
                    unit=args.unit,
                    limit=args.limit,
                )
            else:
                records = source.fetch(
                    resource=args.resource,
                    filters=filters,
                    fields=args.fields,
                    limit=args.limit,
                )
        else:
            records = TdcSource().fetch(task=args.task, name=args.name)
        write_records(records, args.output or _default_output(args.source, args))
    except (ImportError, RuntimeError, ValueError) as error:
        print(f"datamagpie: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
