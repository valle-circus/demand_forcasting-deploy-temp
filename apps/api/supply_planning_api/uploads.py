from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from .errors import ValidationError

_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SavedUpload:
    path: Path
    file_name: str
    size_bytes: int
    sha256: str


async def save_uploads(
    uploads: Iterable[UploadFile],
    directory: Path,
    *,
    allowed_suffixes: frozenset[str],
    max_files: int,
    max_total_bytes: int,
) -> tuple[SavedUpload, ...]:
    selected = tuple(uploads)
    if not selected:
        raise ValidationError("Select at least one file to upload.")
    if len(selected) > max_files:
        raise ValidationError(
            f"Select no more than {max_files} files for one import.",
            details={"max_files": max_files},
        )

    directory.mkdir(parents=True, exist_ok=True)
    saved: list[SavedUpload] = []
    total_bytes = 0
    try:
        for index, upload in enumerate(selected, start=1):
            supplied_name = (upload.filename or f"upload-{index}").replace("\\", "/")
            original_name = supplied_name.rsplit("/", maxsplit=1)[-1].strip()
            if not original_name or original_name in {".", ".."}:
                raise ValidationError("Every upload must have a valid file name.")
            suffix = Path(original_name).suffix.casefold()
            if suffix not in allowed_suffixes:
                allowed = ", ".join(sorted(allowed_suffixes))
                raise ValidationError(
                    f"{original_name}: unsupported file type; expected {allowed}."
                )
            destination = directory / f"{index:03d}{suffix}"
            digest = hashlib.sha256()
            size_bytes = 0
            with destination.open("wb") as handle:
                while chunk := await upload.read(_CHUNK_SIZE):
                    size_bytes += len(chunk)
                    total_bytes += len(chunk)
                    if total_bytes > max_total_bytes:
                        raise ValidationError(
                            "The selected upload exceeds the configured size limit.",
                            details={"max_total_bytes": max_total_bytes},
                        )
                    digest.update(chunk)
                    handle.write(chunk)
            saved.append(
                SavedUpload(
                    path=destination,
                    file_name=original_name,
                    size_bytes=size_bytes,
                    sha256=digest.hexdigest(),
                )
            )
    finally:
        for upload in selected:
            await upload.close()
    return tuple(saved)


def combined_content_hash(files: Iterable[SavedUpload]) -> str:
    digest = hashlib.sha256()
    for value in sorted(file.sha256 for file in files):
        digest.update(value.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
