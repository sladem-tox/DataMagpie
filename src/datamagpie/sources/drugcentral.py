"""DrugCentral database integration through BioClients."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DrugCentralSettings:
    """Connection settings for a DrugCentral PostgreSQL database."""

    host: str
    port: str
    database: str
    user: str
    password: str
    schema: str = "public"


class DrugCentralSource:
    """Run BioClients DrugCentral operations against a PostgreSQL database."""

    _operations = {
        "list_structures": ("ListStructures", "table"),
        "list_structures2smiles": ("ListStructures2Smiles", "table"),
        "list_products": ("ListProducts", "table"),
        "list_active_ingredients": ("ListActiveIngredients", "table"),
        "list_indications": ("ListIndications", "table"),
        "list_indication_targets": ("ListIndicationTargets", "table"),
        "list_ddis": ("ListDrugdruginteractions", "table"),
        "list_atcs": ("ListAtcs", "table"),
        "list_synonyms": ("ListSynonyms", "table"),
        "list_xrefs": ("ListXrefs", "table"),
        "list_xref_types": ("ListXrefTypes", "table"),
        "list_targets": ("ListTargets", "table"),
        "get_structure": ("GetStructure", "ids"),
        "get_structure_by_synonym": ("GetStructureBySynonym", "ids"),
        "get_structure_by_xref": ("GetStructureByXref", "ids_xref"),
        "get_structure_xrefs": ("GetStructureXrefs", "ids"),
        "get_structure_products": ("GetStructureProducts", "ids"),
        "get_structure_atcs": ("GetStructureAtcs", "ids"),
        "get_structure_synonyms": ("GetStructureSynonyms", "ids"),
        "get_structure_targets": ("GetStructureTargets", "ids"),
        "get_product_structures": ("GetProductStructures", "ids"),
        "get_indication_structures": ("GetIndicationStructures", "ids"),
        "search_indications": ("SearchIndications", "ids"),
        "search_products": ("SearchProducts", "ids"),
        "get_drugsummary": ("GetDrugSummary", "ids"),
        "get_drugpage": ("GetDrugPage", "single_id"),
        "version": ("Version", "table"),
    }

    def execute(
        self,
        *,
        operation: str,
        settings: DrugCentralSettings,
        ids: list[str] | None = None,
        xref_type: str | None = None,
    ) -> Any:
        if operation not in self._operations:
            supported = ", ".join(sorted(self._operations))
            raise ValueError(f"unsupported DrugCentral operation: {operation}; choose from {supported}")

        try:
            import psycopg2
            from bioclients.drugcentral import Utils
        except ImportError as error:
            raise ImportError(
                "DrugCentral support requires the optional dependencies; "
                "run `uv sync --extra drugcentral`"
            ) from error

        connection = psycopg2.connect(
            host=settings.host,
            port=settings.port,
            dbname=settings.database,
            user=settings.user,
            password=settings.password,
        )
        try:
            function_name, argument_kind = self._operations[operation]
            function = getattr(Utils, function_name, None)
            if function is None:
                raise RuntimeError(
                    f"installed BioClients does not provide DrugCentral operation "
                    f"{operation} ({function_name})"
                )
            if argument_kind == "table":
                return function(connection, settings.schema)
            if argument_kind == "single_id":
                values = ids or []
                if len(values) != 1:
                    raise ValueError(f"{operation} requires exactly one value via --ids")
                return function(connection, values[0])
            if argument_kind == "ids_xref":
                if not ids:
                    raise ValueError(f"{operation} requires --ids")
                if not xref_type:
                    raise ValueError(f"{operation} requires --xref-type")
                return function(connection, ids, xref_type)
            if not ids:
                raise ValueError(f"{operation} requires --ids")
            return function(connection, ids)
        finally:
            connection.close()

    @classmethod
    def settings_from_file(cls, path: Path) -> DrugCentralSettings:
        try:
            import yaml
        except ImportError as error:
            raise ImportError(
                "reading DrugCentral configuration requires PyYAML; "
                "run `uv sync --extra drugcentral`"
            ) from error
        if not path.exists():
            raise ValueError(f"DrugCentral configuration file does not exist: {path}")
        values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        required = {
            "host": values.get("DBHOST"),
            "port": values.get("DBPORT"),
            "database": values.get("DBNAME"),
            "user": values.get("DBUSR"),
            "password": values.get("DBPW"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"DrugCentral configuration is missing: {', '.join(missing)}"
            )
        return cls(**required, schema=values.get("DBSCHEMA", "public"))
