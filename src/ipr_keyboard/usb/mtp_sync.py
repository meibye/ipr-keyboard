from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class SyncResult:
    copied: list[Path]
    skipped: list[Path]
    deleted_source: list[Path]


def _iter_text_files(root: Path) -> Iterable[Path]:
    """Yield all *.txt files under root (non-recursive or recursive depending on your liking)."""
    # If IrisPen stores everything flat, non-recursive is enough:
    # for path in root.glob("*.txt"):
    #     yield path

    # If it has subfolders, use recursive:
    for path in root.rglob("*.txt"):
        if path.is_file():
            yield path


def sync_mtp_to_cache(
    mtp_root: Path,
    cache_root: Path,
    delete_source: bool = False,
) -> SyncResult:
    """
    Sync *.txt files from an MTP-mounted root into a local cache directory.

    - Copies files that are new or have a different size/mtime.
    - Optionally deletes source files on success.
    """
    mtp_root = mtp_root.resolve()
    cache_root = cache_root.resolve()
    cache_root.mkdir(parents=True, exist_ok=True)

    copied: list[Path] = []
    skipped: list[Path] = []
    deleted_source: list[Path] = []

    for src in _iter_text_files(mtp_root):
        rel = src.relative_to(mtp_root)
        dst = cache_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        if dst.exists():
            src_stat = src.stat()
            dst_stat = dst.stat()
            if (
                src_stat.st_size == dst_stat.st_size
                and int(src_stat.st_mtime) == int(dst_stat.st_mtime)
            ):
                skipped.append(src)
                continue

        shutil.copy2(src, dst)
        copied.append(src)

        if delete_source:
            try:
                src.unlink()
                deleted_source.append(src)
            except OSError:
                # Log from caller if needed
                pass

    return SyncResult(copied=copied, skipped=skipped, deleted_source=deleted_source)


def main() -> None:
    """
    CLI entry point: sync from /mnt/irispen to ./cache/irispen by default.
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Sync IrisPen text files from MTP mount to local cache."
    )
    parser.add_argument(
        "--mtp-root",
        default="/mnt/irispen",
        help="Path where IrisPen is mounted via jmtpfs (default: /mnt/irispen)",
    )
    parser.add_argument(
        "--cache-root",
        default="./cache/irispen",
        help="Local cache folder (default: ./cache/irispen)",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete source files on IrisPen after successful copy.",
    )

    args = parser.parse_args()
    mtp_root = Path(args.mtp_root)
    cache_root = Path(args.cache_root)

    if not mtp_root.exists():
        print(f"[mtp_sync] ERROR: MTP root {mtp_root} does not exist", file=sys.stderr)
        sys.exit(1)

    res = sync_mtp_to_cache(mtp_root, cache_root, delete_source=args.delete_source)

    print(f"[mtp_sync] Copied {len(res.copied)} file(s)")
    print(f"[mtp_sync] Skipped {len(res.skipped)} file(s)")
    if args.delete_source:
        print(f"[mtp_sync] Deleted {len(res.deleted_source)} source file(s)")


if __name__ == "__main__":
    main()
