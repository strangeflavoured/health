"""Domain models for upload failure tracking and duplicate-write policy.

This module defines:

* :class:`DuplicatePolicy` — Redis TimeSeries write-conflict strategy.
* :class:`RowFailure` — a failed upload for a single DataFrame row.
* :class:`BatchFailure` — a failed upload for an entire data-type batch.
* :data:`UploadFailure` — union alias consumed by the pipeline and importer.
* :func:`failures_to_json` / :func:`failures_from_json` — persistence helpers.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DuplicatePolicy(Enum):
    """Redis TimeSeries per-command duplicate-write strategy.

    :attr:`FIRST` is used by :meth:`~HealthDataImporter.etl` for initial
    imports so that re-running an export never overwrites existing data points.
    It is also used by :meth:`~HealthDataImporter.retry_failed`.

    :attr:`LAST` is used by :meth:`~HealthDataImporter.update` to overwrite
    existing data points with new values.

    Example::

        policy = DuplicatePolicy.FIRST
        pipe.add(key="hr:start", timestamp=ts, value=v,
                 duplicate_policy=policy.value)
    """

    FIRST = "FIRST"
    LAST = "LAST"


# ---------------------------------------------------------------------------
# Failure dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RowFailure:
    """Records a failed upload for a single DataFrame row.

    Produced by :func:`~pipeline.upload_batch` when one or both ``TS.ADD``
    commands for a specific row return a
    :class:`~redis.exceptions.ResponseError` inside the pipeline response
    (i.e. the connection itself stayed up, but that individual command failed).

    Attributes::

        data_type: The ``data_type`` column value for this row, e.g.
            ``"HKQuantityTypeIdentifierHeartRate"``.
        row_index: The pandas DataFrame index label of the failed row.
            Use ``df.loc[failure.row_index]`` to retrieve the full row.
        start_error: Human-readable message from the
            :class:`~redis.exceptions.ResponseError` for the ``<type>:start``
            command, or ``None`` if that command succeeded.
        end_error: Human-readable message from the
            :class:`~redis.exceptions.ResponseError` for the ``<type>:end``
            command, or ``None`` if that command succeeded.

    Example::

        f = RowFailure(data_type="HKQuantityTypeIdentifierHeartRate",
                       row_index=42, start_error="TSDB: Duplicate")
    """

    data_type: str
    row_index: Any
    start_error: str | None = field(default=None)
    end_error: str | None = field(default=None)

    def __str__(self) -> str:
        """Create human-readable string representation of this failure.

        Returns:
             String in the form RowFailure(data_type=..., row_index=..., errors=[...]).

        """
        errors: list[str] = []
        if self.start_error is not None:
            errors.append(f"start={self.start_error!r}")
        if self.end_error is not None:
            errors.append(f"end={self.end_error!r}")
        return (
            f"RowFailure(data_type={self.data_type!r}, "
            f"row_index={self.row_index!r}, "
            f"errors=[{', '.join(errors)}])"
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary.

        Returns:
            A plain ``dict`` with keys ``kind``, ``data_type``,
            ``row_index``, ``start_error``, and ``end_error``.

        Example::

            RowFailure("HR", 0, start_error="err").to_dict()
            # → {"kind": "row", "data_type": "HR", "row_index": 0,
            #    "start_error": "err", "end_error": None}

        """
        return {
            "kind": "row",
            "data_type": self.data_type,
            "row_index": self.row_index,
            "start_error": self.start_error,
            "end_error": self.end_error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RowFailure":
        """Deserialise from a dictionary produced by :meth:`to_dict`.

        Args:
            d: Dictionary with ``data_type``, ``row_index``, ``start_error``,
                and ``end_error`` keys.

        Returns:
            A :class:`RowFailure` instance.

        Example::

            RowFailure.from_dict({"data_type": "HR", "row_index": 0,
                                  "start_error": None, "end_error": None})

        """
        return cls(
            data_type=d["data_type"],
            row_index=d["row_index"],
            start_error=d.get("start_error"),
            end_error=d.get("end_error"),
        )
