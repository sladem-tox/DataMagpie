"""Downloader for the public CT-ADE benchmark releases."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CtAdeSource:
    """Download CT-ADE-SOC or CT-ADE-PT files from Hugging Face."""

    _datasets = {
        "soc": "CT-ADE-SOC",
        "pt": "CT-ADE-PT",
    }
    _splits = ("train", "val", "test")

    def download(
        self,
        *,
        version: str,
        output_dir: Path,
        splits: list[str] | None = None,
        include_frequencies: bool = False,
    ) -> list[Path]:
        if version not in self._datasets:
            raise ValueError("CT-ADE version must be 'soc' or 'pt'")
        selected_splits = splits or list(self._splits)
        invalid = sorted(set(selected_splits) - set(self._splits))
        if invalid:
            raise ValueError(f"invalid CT-ADE split(s): {', '.join(invalid)}")

        dataset_name = self._datasets[version]
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []
        filenames = [
            f"{split}{'_frequencies' if include_frequencies else ''}.csv"
            for split in selected_splits
        ]
        for filename in filenames:
            url = (
                f"https://huggingface.co/datasets/anthonyyazdaniml/"
                f"{dataset_name}/resolve/main/{filename}"
            )
            destination = output_dir / filename
            self._download_file(url, destination)
            downloaded.append(destination)

        manifest = {
            "source": "CT-ADE",
            "version": version.upper(),
            "dataset": f"anthonyyazdaniml/{dataset_name}",
            "revision": "main",
            "files": [
                {
                    "path": str(path.relative_to(output_dir)),
                    "url": (
                        f"https://huggingface.co/datasets/anthonyyazdaniml/"
                        f"{dataset_name}/blob/main/{path.name}"
                    ),
                }
                for path in downloaded
            ],
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        downloaded.append(manifest_path)
        return downloaded

    @staticmethod
    def _download_file(url: str, destination: Path) -> None:
        request = Request(url, headers={"User-Agent": "DataMagpie/0.1"})
        try:
            with urlopen(request) as response, destination.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        except (HTTPError, URLError, OSError) as error:
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"failed to download {url}: {error}") from error
