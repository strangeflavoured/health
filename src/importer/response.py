"""Domain models for upload failure tracking and duplicate-write policy.

This module defines:

* :class:`DuplicatePolicy` — Redis TimeSeries write-conflict strategy.
* :class:`RowFailure` — a failed upload for a single DataFrame row.
* :class:`BatchFailure` — a failed upload for an entire data-type batch.
* :data:`UploadFailure` — union alias consumed by the pipeline and importer.
* :func:`failures_to_json` / :func:`failures_from_json` — persistence helpers.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DuplicatePolicy(Enum):
    """Redis TimeSeries per-command duplicate-write strategy.

    :attr:`FIRST` is used by :meth:`~.importer.HealthDataImporter.etl` for initial
    imports so that re-running an export never overwrites existing data points.
    It is also used by :meth:`~.importer.HealthDataImporter.retry_failed`.

    :attr:`LAST` is used by :meth:`~.importer.HealthDataImporter.update` to overwrite
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

    Produced by :func:`~.pipeline.upload_batch` when one or both ``TS.ADD``
    commands for a specific row return a :class:`~redis.exceptions.ResponseError`
    inside the pipeline response (i.e. the connection itself stayed up, but that
    individual command failed).

    Attributes:
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


@dataclass
class BatchFailure:
    """Records a failed upload for an entire data-type batch.

    Produced by :func:`~.pipeline.upload_batch` when the pipeline itself
    raises a :class:`~redis.exceptions.RedisError` (e.g. a connection
    failure, authentication error, or server-side crash).  In this case no
    row-level response is available, so the entire batch is marked failed.

    Attributes:
        data_type: The ``data_type`` column value for this batch, e.g.
            ``"HKQuantityTypeIdentifierHeartRate"``.
        error: Human-readable message from the
            :class:`~redis.exceptions.RedisError` that was raised.

    Example::

        f = BatchFailure(data_type="HKQuantityTypeIdentifierHeartRate",
                         error="Connection reset by peer")

    """

    data_type: str
    error: str

    def __str__(self) -> str:
        """Create human-readable string representation of this failure.

        Returns:
             String in the form BatchFailure(data_type=..., errors=[...]).

        """
        return f"BatchFailure(data_type={self.data_type!r}, error={self.error!r})"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-compatible dictionary.

        Returns:
            A plain ``dict`` with keys ``kind``, ``data_type``, and ``error``.

        Example::

            BatchFailure("HR", "timeout").to_dict()
            # → {"kind": "batch", "data_type": "HR", "error": "timeout"}

        """
        return {
            "kind": "batch",
            "data_type": self.data_type,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BatchFailure":
        """Deserialise from a dictionary produced by :meth:`to_dict`.

        Args:
            d: Dictionary with ``data_type`` and ``error`` keys.

        Returns:
            A :class:`BatchFailure` instance.

        Example::

            BatchFailure.from_dict({"data_type": "HR", "error": "timeout"})

        """
        return cls(
            data_type=d["data_type"],
            error=d["error"],
        )


#: Union type for a single upload failure — either a row-level or batch-level
#: failure.  Used as the element type of the failures list returned by
#: :meth:`~HealthDataImporter._load` and stored on the importer instance.
UploadFailure = RowFailure | BatchFailure


# ---------------------------------------------------------------------------
# JSON persistence helpers
# ---------------------------------------------------------------------------


def failures_to_json(failures: list[UploadFailure]) -> str:
    """Serialise a list of :class:`UploadFailure` objects to a JSON string.

    Args:
        failures: List of :class:`RowFailure` or :class:`BatchFailure` objects.

    Returns:
        A pretty-printed JSON string suitable for writing to disk.

    Example::

        text = failures_to_json([BatchFailure("HR", "timeout")])
        Path("failures.json").write_text(text)

    """
    return json.dumps([f.to_dict() for f in failures], indent=2)


def failures_from_json(text: str) -> list[UploadFailure]:
    """Deserialise a JSON string produced by :func:`failures_to_json`.

    Args:
        text: JSON string as written by :func:`failures_to_json`.

    Returns:
        List of :class:`RowFailure` and/or :class:`BatchFailure` objects.

    Raises:
        ValueError: If an entry has an unknown ``kind`` value.

    Example::

        failures = failures_from_json(Path("failures.json").read_text())

    """
    failures: list[UploadFailure] = []
    for entry in json.loads(text):
        kind = entry.get("kind")
        if kind == "row":
            failures.append(RowFailure.from_dict(entry))
        elif kind == "batch":
            failures.append(BatchFailure.from_dict(entry))
        else:
            raise ValueError(
                f"Unknown failure kind {kind!r} in failures file. "
                "File may be corrupted."
            )
    return failures
