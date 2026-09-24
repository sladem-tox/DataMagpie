"""Therapeutics Data Commons integration."""

from __future__ import annotations

from typing import Any


class TdcSource:
    """Load named datasets from the main TDC prediction task families."""

    _TASKS = {
        "adme": ("tdc.single_pred", "ADME"),
        "tox": ("tdc.single_pred", "Tox"),
        "dti": ("tdc.multi_pred", "DTI"),
        "hts": ("tdc.multi_pred", "HTS"),
        "drugres": ("tdc.multi_pred", "DrugRes"),
    }

    def fetch(self, *, task: str, name: str) -> list[dict[str, Any]]:
        try:
            module_name, class_name = self._TASKS[task]
        except KeyError as error:
            raise ValueError(f"unsupported TDC task: {task}") from error

        try:
            module = __import__(module_name, fromlist=[class_name])
            dataset_class = getattr(module, class_name)
        except (ImportError, AttributeError) as error:
            raise ImportError(
                "the TDC client is unavailable or does not provide this task; "
                "install/update PyTDC"
            ) from error

        dataset = dataset_class(name=name)
        frame = dataset.get_data(format="df")
        return frame.to_dict(orient="records")
