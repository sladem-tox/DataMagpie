"""Public Tox21 Gateway data integration."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Tox21Source:
    """Query the public Tox21 Gateway and download assay archives."""

    _base_url = "https://tripod.nih.gov/pubdata"
    _portal_url = "https://tripod.nih.gov/tox"
    _download_base_url = "https://opendata.ncats.nih.gov/public/tox21/assay/data"

    def list_assays(self) -> list[dict[str, object]]:
        return self._get_json("/route/data/assays")

    def search(
        self,
        *,
        query: str,
        query_type: str,
        view: str,
        protocols: list[str] | None,
        limit: int,
    ) -> list[dict[str, object]]:
        if query_type not in {"name", "id"}:
            raise ValueError("Tox21 query type must be 'name' or 'id'")
        if view not in {"replicate", "aggregated"}:
            raise ValueError("Tox21 view must be 'replicate' or 'aggregated'")
        if limit < 1:
            raise ValueError("--limit must be greater than zero")

        endpoint = f"/route/data/search/{view}/by{query_type}"
        if query_type == "name":
            params = {"chemName": query}
        else:
            params = {"type": "TOX21_ID", "ids": query}
        params.update(
            {
                "protocols": ";".join(protocols or []),
                "recordstartindex": "0",
                "recordendindex": str(limit),
                "pagesize": str(limit),
            }
        )
        payload = self._get_json(endpoint, params)
        if not isinstance(payload, list) or not payload:
            return []
        first = payload[0]
        if not isinstance(first, dict):
            raise RuntimeError("unexpected Tox21 search response")
        rows = first.get("Rows", [])
        if not isinstance(rows, list):
            raise RuntimeError("unexpected Tox21 search rows")
        return rows

    def download_assay(self, *, protocol: str, output: Path) -> Path:
        if not protocol.strip():
            raise ValueError("protocol must not be empty")
        output.parent.mkdir(parents=True, exist_ok=True)
        url = f"{self._download_base_url}/{protocol}.zip"
        self._download_file(url, output)
        return output

    def assay_description(self, *, protocol: str) -> object:
        return self._get_json(
            f"/route/assays/desc/{protocol}",
            base_url=self._portal_url,
        )

    def _get_json(
        self,
        path: str,
        params: dict[str, str] | None = None,
        base_url: str | None = None,
    ) -> object:
        url = f"{base_url or self._base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "DataMagpie/0.1"})
        try:
            with urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"failed to query Tox21: {error}") from error

    @staticmethod
    def _download_file(url: str, destination: Path) -> None:
        request = Request(url, headers={"User-Agent": "DataMagpie/0.1"})
        try:
            with urlopen(request) as response, destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        except (HTTPError, URLError, OSError) as error:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"failed to download Tox21 assay archive: {error}") from error
