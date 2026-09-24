# DataMagpie

DataMagpie is a command-line toolkit for downloading data from biomedical data
sources. Integrations live in separate modules so additional providers can be
added without changing the command-line output format.

![A magpie representing the DataMagpie project](images/Magpie-con.jpg)



Downloaded files are stored in the local `data/` directory by default. The
directory is retained in the repository with `.keep`, while downloaded files
are ignored by Git.

## Installation

```bash
uv sync
```

To enable the TDC integration, install its optional dependency:

```bash
uv sync --extra tdc
```

## ChEMBL

Query a ChEMBL resource with repeated `KEY=VALUE` filters:

```bash
datamagpie chembl --resource molecule --filter pref_name__iexact=aspirin \
  --field molecule_chembl_id --field pref_name
```

This writes to `data/chembl_molecule.json`. Use `--output` to choose a
different path or format, for example `--output data/aspirin.csv`.

Use `--count` to check the number of matching records without writing a
download:

```bash
datamagpie chembl --resource molecule \
  --filter pref_name__iexact=aspirin --count
```

For target bioactivity searches, use `--target-query`. DataMagpie searches
ChEMBL targets, tries the first five matches, and selects the first target with
records for the requested standard type:

```bash
datamagpie chembl \
  --target-query "PXR inhibition" \
  --standard-type IC50 \
  --unit nM \
  --count
```

Remove `--count` to download the records. The default standard type is `IC50`;
the optional unit filter can be set to `nM`.

## Cleaning bioactivity data

Cleaning is a separate step so raw downloads remain available for auditing or
reprocessing:

```bash
datamagpie clean-bioactivity \
  --input data/chembl_bioactivity_PXR_inhibition.json
```

The default output is
`data/chembl_bioactivity_PXR_inhibition_cleaned.csv`. Cleaning removes missing,
non-numeric, non-positive, and invalid-unit values; retains `IC50` records in
`nM`; deduplicates by SMILES; assigns `active`, `intermediate`, or `inactive`
labels using the default bins `0`, `1000`, `10000`, and `1000000` nM; and adds
`pIC50`. Use `--bins` and `--label` to provide alternative classification
thresholds and labels.

The `--resource` value is resolved against the resources exposed by
`chembl_webresource_client.new_client`, so the same command supports resources
such as `molecule`, `target`, and `assay`.

## Therapeutics Data Commons

Download a named dataset from a supported TDC task family:

```bash
datamagpie tdc --task adme --name Caco2_Wang --output caco2.csv
```

Supported task families are `adme`, `tox`, `dti`, `hts`, and `drugres`.
Results are written as JSON by default, or as CSV when the output path ends in
`.csv`.
