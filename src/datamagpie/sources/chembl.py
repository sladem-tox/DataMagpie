"""ChEMBL WebResource Client integration."""

from __future__ import annotations

from typing import Any


class ChemblSource:
    """Fetch records from any resource exposed by the ChEMBL client."""

    def _query(
        self,
        *,
        resource: str,
        filters: dict[str, str],
    ) -> Any:
        try:
            from chembl_webresource_client.new_client import new_client
        except ImportError as error:
            raise ImportError(
                "the ChEMBL client is unavailable; install the project dependencies"
            ) from error

        client_resource = getattr(new_client, resource, None)
        if client_resource is None:
            raise ValueError(f"unknown ChEMBL resource: {resource}")
        return client_resource.filter(**filters) if filters else client_resource

    def count(self, *, resource: str, filters: dict[str, str]) -> int:
        """Return the number of records matching a ChEMBL query."""
        return len(self._query(resource=resource, filters=filters))

    def _target_candidates(self, target_query: str) -> list[dict[str, Any]]:
        results = self._query(resource="target", filters={})
        targets = [dict(record) for record in results.search(target_query)]
        if not targets:
            raise ValueError(f"No ChEMBL targets found for query '{target_query}'.")
        return targets[:5]

    def fetch_bioactivity(
        self,
        *,
        target_query: str,
        standard_type: str = "IC50",
        unit: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch bioactivity records for the first matching target with data."""
        if limit is not None and limit < 0:
            raise ValueError("--limit must be zero or greater")

        candidates = self._target_candidates(target_query)
        activity = self._query(resource="activity", filters={})
        for candidate in candidates:
            candidate_id = candidate.get("target_chembl_id")
            if not candidate_id:
                continue
            filters = {
                "target_chembl_id": candidate_id,
                "standard_type": standard_type,
            }
            if unit:
                filters["standard_units"] = unit
            records = activity.filter(**filters)
            if limit is not None:
                records = records[:limit]
            rows = [dict(record) for record in records]
            if rows:
                return rows

        raise ValueError(
            f"None of the top {len(candidates)} ChEMBL targets matching "
            f"'{target_query}' have {standard_type} bioactivity records."
        )

    def count_bioactivity(
        self,
        *,
        target_query: str,
        standard_type: str = "IC50",
        unit: str | None = None,
    ) -> int:
        """Count bioactivity records for the first matching target with data."""
        candidates = self._target_candidates(target_query)
        activity = self._query(resource="activity", filters={})
        for candidate in candidates:
            candidate_id = candidate.get("target_chembl_id")
            if not candidate_id:
                continue
            filters = {
                "target_chembl_id": candidate_id,
                "standard_type": standard_type,
            }
            if unit:
                filters["standard_units"] = unit
            count = len(activity.filter(**filters))
            if count:
                return count
        raise ValueError(
            f"None of the top {len(candidates)} ChEMBL targets matching "
            f"'{target_query}' have {standard_type} bioactivity records."
        )

    def fetch(
        self,
        *,
        resource: str,
        filters: dict[str, str],
        fields: list[str] | None,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        if limit is not None and limit < 0:
            raise ValueError("--limit must be zero or greater")

        query = self._query(resource=resource, filters=filters)
        if fields:
            query = query.only(fields)
        if limit is not None:
            query = query[:limit]
        return [dict(record) for record in query]
