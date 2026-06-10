#!/usr/bin/env python3
"""
migrate_media_to_pcloud.py

Scans the org-data directory tree for media folders, moves all media files
to a mirrored directory structure at a given destination (e.g. pCloud), and
replaces each media folder with a symlink pointing to the destination.

Usage:
    python migrate_media_to_pcloud.py <repo_root> <destination_root>

Example:
    python migrate_media_to_pcloud.py . ~/pCloudDrive/strollopia-media

Directory structure expected:
    <repo_root>/org-data/<project-domain>/<map-name>/media/<files>

After migration:
    <repo_root>/org-data/<project-domain>/<map-name>/media  -> symlink
    <destination_root>/org-data/<project-domain>/<map-name>/media/<files>
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime


def find_media_folders(org_data_path: Path) -> list[Path]:
    """
    Walk org-data and return all paths matching:
      org-data/<project-domain>/<map-name>/media
    """
    media_folders = []
    # Depth: org-data / domain / map-name / media
    for domain_dir in sorted(org_data_path.iterdir()):
        if not domain_dir.is_dir():
            continue
        for map_dir in sorted(domain_dir.iterdir()):
            if not map_dir.is_dir():
                continue
            media_dir = map_dir / "media"
            if media_dir.exists() and media_dir.is_dir() and not media_dir.is_symlink():
                media_folders.append(media_dir)
    return media_folders


def file_size_str(path: Path) -> str:
    """Return human-readable file size."""
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def step(n: int, text: str, dry_run: bool):
    prefix = "  [DRY RUN] " if dry_run else "  "
    print(f"{prefix}Step {n}: {text}")


def migrate_media_folder(
    media_src: Path,
    repo_root: Path,
    dest_root: Path,
    dry_run: bool,
    log: list[dict],
):
    """
    For a single media folder:
      1. Compute the mirrored destination path.
      2. Create destination directory tree.
      3. Move all files to destination.
      4. Remove now-empty source directory.
      5. Create symlink source -> destination.
    """
    rel_path = media_src.relative_to(repo_root)
    dest_media = dest_root / rel_path

    files = [f for f in sorted(media_src.iterdir()) if f.is_file()]
    if not files:
        print(f"\n  [SKIP] {rel_path}  — media folder is empty, nothing to do.")
        return

    total_size = sum(f.stat().st_size for f in files)
    total_mb = total_size / (1024 * 1024)

    print(f"\n{'─'*60}")
    print(f"  Folder : {rel_path}")
    print(f"  Files  : {len(files)}  ({total_mb:.1f} MB total)")
    print()

    # Step 1: Show destination directory creation
    step(1, f"Create destination directory (if it doesn't exist):", dry_run)
    print(f"           {dest_media}")
    if not dry_run:
        dest_media.mkdir(parents=True, exist_ok=True)

    # Step 2: Move each file
    step(2, f"Move {len(files)} file(s) from repo → pCloud:", dry_run)
    entry = {
        "source_symlink": str(media_src),
        "destination": str(dest_media),
        "files": [],
    }
    for f in files:
        dest_file = dest_media / f.name
        size_str = file_size_str(f)
        print(f"           {f.name}  ({size_str})")
        print(f"           → {dest_file}")
        entry["files"].append(f.name)
        if not dry_run:
            shutil.move(str(f), str(dest_file))

    # Step 3: Remove the now-empty source directory
    step(3, f"Delete the now-empty source directory:", dry_run)
    print(f"           rm -rf {media_src}")
    if not dry_run:
        try:
            media_src.rmdir()
        except OSError as e:
            print(f"  [WARN] Could not remove source dir (may not be empty): {e}")
            return

    # Step 4: Create symlink
    step(4, f"Create symlink in its place:", dry_run)
    print(f"           {media_src}")
    print(f"           → {dest_media.resolve()}")
    if not dry_run:
        media_src.symlink_to(dest_media.resolve())
        print(f"  ✓ Done.")

    log.append(entry)


def write_readme(repo_root: Path, dest_root: Path, log: list[dict]):
    """Write README_symlink.md at the repo root explaining the migration."""
    readme_path = repo_root / "README_symlink.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# Media File Symlinks",
        "",
        f"Generated: {now}",
        "",
        "## What happened",
        "",
        "Large media files (videos, images, etc.) have been moved out of this git",
        "repository to avoid exceeding GitHub's 100 MB file size limit.",
        "",
        "They now live in an external storage location (pCloud) and each original",
        "`media/` folder inside the repo has been replaced with a **symlink** pointing",
        "to the corresponding folder in that external storage.",
        "",
        "Git commits the symlink (just a path pointer) — not the files themselves.",
        "",
        "## Storage location",
        "",
        f"All media files are stored under:",
        f"```",
        f"{dest_root}",
        f"```",
        "",
        "The folder structure mirrors the repo exactly:",
        "```",
        "org-data/<project-domain>/<map-name>/media/<file>",
        "```",
        "",
        "## First-time setup (restoring symlinks on a new machine)",
        "",
        "1. **Install and sign in to [pCloud Drive](https://www.pcloud.com/download-free-online-cloud-storage.html)**",
        f"   The drive should mount so that `{dest_root}` is accessible.",
        "",
        "2. **Run the setup script** from the repo root to recreate all symlinks:",
        "",
        "   ```bash",
        "   python migrate_media_to_pcloud.py . <destination_root> --relink-only",
        "   ```",
        "",
        "   Or recreate them manually — for each entry below:",
        "   ```bash",
        "   ln -s <destination> <source_symlink>",
        "   ```",
        "",
        "3. **Verify** a symlink is working:",
        "   ```bash",
        "   ls -la org-data/<domain>/<map>/media",
        "   ```",
        "   You should see an arrow (`->`) pointing to the pCloud path.",
        "",
        "## Migrated folders",
        "",
    ]

    for entry in log:
        rel_link = Path(entry["source_symlink"]).relative_to(repo_root)
        lines.append(f"### `{rel_link}`")
        lines.append(f"- **Symlink:** `{entry['source_symlink']}`")
        lines.append(f"- **Destination:** `{entry['destination']}`")
        lines.append(f"- **Files ({len(entry['files'])}):**")
        for fname in entry["files"]:
            lines.append(f"  - `{fname}`")
        lines.append("")

    readme_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  ✓ README written: {readme_path}")


def revert(repo_root: Path, dry_run: bool):
    """
    Undo a previous migration by reading README_symlink.md:
      1. Remove each symlink from the repo.
      2. Re-create the media/ directory.
      3. Move all files back from pCloud to the repo.
      4. Delete the now-empty pCloud directory.
    """
    readme_path = repo_root / "README_symlink.md"
    if not readme_path.exists():
        print("ERROR: README_symlink.md not found — nothing to revert.")
        print(f"  Expected at: {readme_path}")
        sys.exit(1)

    # Parse README_symlink.md to extract symlink → destination → files entries
    entries = []
    current = None
    for line in readme_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### `"):
            if current:
                entries.append(current)
            current = {"source_symlink": None, "destination": None, "files": []}
        elif current and line.startswith("- **Symlink:**"):
            current["source_symlink"] = line.split("`")[1]
        elif current and line.startswith("- **Destination:**"):
            current["destination"] = line.split("`")[1]
        elif current and line.strip().startswith("- `") and current["destination"]:
            fname = line.strip()[3:-1]
            if fname:
                current["files"].append(fname)
    if current:
        entries.append(current)

    if not entries:
        print("ERROR: Could not parse any entries from README_symlink.md.")
        sys.exit(1)

    print(f"{'═'*60}")
    if dry_run:
        print("  REVERT DRY RUN — no files will be moved")
    else:
        print("  REVERT — symlinks will be removed, files moved back to repo")
    print(f"{'═'*60}")
    print(f"  Found {len(entries)} entry/entries in README_symlink.md")
    print()

    for entry in entries:
        src = Path(entry["source_symlink"])
        dest = Path(entry["destination"])
        files = entry["files"]

        rel = src.relative_to(repo_root)
        print(f"\n{'─'*60}")
        print(f"  Folder : {rel}")
        print(f"  Files  : {len(files)}")
        print()

        # Step 1: Remove the symlink
        step(1, "Remove symlink from repo:", dry_run)
        print(f"           unlink {src}")
        if not dry_run:
            if src.is_symlink():
                src.unlink()
            elif not src.exists():
                print(f"  [WARN] Symlink not found at {src} — skipping unlink.")
            else:
                print(f"  [WARN] {src} exists but is not a symlink — skipping.")
                continue

        # Step 2: Re-create the media/ directory in the repo
        step(2, "Re-create media/ directory in repo:", dry_run)
        print(f"           mkdir {src}")
        if not dry_run:
            src.mkdir(parents=True, exist_ok=True)

        # Step 3: Move files back
        step(3, f"Move {len(files)} file(s) from pCloud → repo:", dry_run)
        for fname in files:
            src_file = dest / fname
            dest_file = src / fname
            size_str = file_size_str(src_file) if src_file.exists() else "?"
            print(f"           {fname}  ({size_str})")
            print(f"           → {dest_file}")
            if not dry_run:
                if src_file.exists():
                    shutil.move(str(src_file), str(dest_file))
                else:
                    print(f"  [WARN] File not found in pCloud: {src_file}")

        # Step 4: Remove now-empty pCloud directory
        step(4, "Remove now-empty pCloud directory:", dry_run)
        print(f"           rm -rf {dest}")
        if not dry_run:
            try:
                dest.rmdir()
            except OSError:
                print(f"  [WARN] Could not remove {dest} — may not be empty.")

        if not dry_run:
            print(f"  ✓ Done.")

    if dry_run:
        print(f"\n{'═'*60}")
        print("  DRY RUN SUMMARY — nothing was changed")
        print(f"{'═'*60}")
        print("  If you run with --revert (without --dry-run), the script will:")
        print("    1. Remove each symlink from the repo")
        print("    2. Re-create each media/ directory")
        print("    3. Move all files back from pCloud into the repo")
        print("    4. Delete the now-empty pCloud directories")
        print()
        print("  Then re-run the migration with the correct destination:")
        print("    python migrate_media_to_pcloud.py . ~/pCloudDrive/CORRECT-NAME")
    else:
        # Remove the README since state is reverted
        readme_path.unlink()
        print(f"\n{'═'*60}")
        print("  ✅ Revert complete — repo is back to its original state")
        print(f"{'═'*60}")
        print("  README_symlink.md has been removed.")
        print()
        print("  Now re-run the migration with the correct destination folder:")
        print("    python migrate_media_to_pcloud.py . ~/pCloudDrive/CORRECT-FOLDER-NAME")


def relink_only(repo_root: Path, dest_root: Path):
    """
    Re-create symlinks from the README_symlink.md on a fresh machine.
    Finds all media dirs in dest_root and symlinks them back into the repo.
    """
    org_data = repo_root / "org-data"
    if not org_data.exists():
        print("ERROR: org-data directory not found.")
        sys.exit(1)

    count = 0
    for domain_dir in sorted((dest_root / "org-data").iterdir()):
        if not domain_dir.is_dir():
            continue
        for map_dir in sorted(domain_dir.iterdir()):
            if not map_dir.is_dir():
                continue
            media_dest = map_dir / "media"
            if not media_dest.is_dir():
                continue
            rel = media_dest.relative_to(dest_root)
            media_link = repo_root / rel
            if media_link.exists() or media_link.is_symlink():
                print(f"  [SKIP] Already exists: {media_link}")
                continue
            media_link.parent.mkdir(parents=True, exist_ok=True)
            media_link.symlink_to(media_dest.resolve())
            print(f"  ✓ Linked: {media_link} → {media_dest.resolve()}")
            count += 1

    print(f"\nDone. {count} symlink(s) created.")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate org-data media folders to pCloud and replace with symlinks."
    )
    parser.add_argument(
        "repo_root",
        help="Path to the root of the git repository",
    )
    parser.add_argument(
        "destination_root",
        help="Path to the destination root (e.g. ~/pCloudDrive/strollopia-media)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without moving any files",
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Undo a previous migration: remove symlinks and move files back to repo",
    )
    parser.add_argument(
        "--relink-only",
        action="store_true",
        help="Only recreate symlinks from existing pCloud structure (for new machine setup)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    dest_root = Path(args.destination_root).expanduser().resolve()

    if not repo_root.exists():
        print(f"ERROR: repo_root does not exist: {repo_root}")
        sys.exit(1)

    org_data = repo_root / "org-data"
    if not org_data.exists():
        print(f"ERROR: No org-data directory found at: {org_data}")
        sys.exit(1)

    if args.revert:
        revert(repo_root, dry_run=args.dry_run)
        return

    if args.relink_only:
        print(f"Re-linking mode: {dest_root} → {repo_root}")
        relink_only(repo_root, dest_root)
        return

    print(f"{'═'*60}")
    if args.dry_run:
        print("  DRY RUN — no files will be moved or symlinks created")
    else:
        print("  MIGRATION — files will be moved and symlinks created")
    print(f"{'═'*60}")
    print(f"  Repo root   : {repo_root}")
    print(f"  Destination : {dest_root}")
    print()

    media_folders = find_media_folders(org_data)

    if not media_folders:
        print("No media folders found under org-data/. Nothing to do.")
        sys.exit(0)

    print(f"Found {len(media_folders)} media folder(s):")
    for mf in media_folders:
        print(f"  {mf.relative_to(repo_root)}")

    log = []
    for media_src in media_folders:
        migrate_media_folder(media_src, repo_root, dest_root, args.dry_run, log)

    if args.dry_run:
        total_files = sum(len(e["files"]) for e in log)
        print(f"\n{'═'*60}")
        print(f"  DRY RUN SUMMARY — nothing was changed")
        print(f"{'═'*60}")
        print(f"  Folders to migrate : {len(log)}")
        print(f"  Files to move      : {total_files}")
        print()
        print("  If you run without --dry-run, the script will:")
        print("    1. Create the mirrored directory tree under:")
        print(f"       {dest_root}")
        print("    2. Move every media file into that tree")
        print("    3. Delete each empty media/ directory from the repo")
        print("    4. Create a symlink at each media/ location pointing to pCloud")
        print("    5. Write README_symlink.md documenting every symlink")
        print()
        print("  Then you would commit with:")
        print("    git add org-data README_symlink.md")
        print("    git commit -m 'Migrate media files to pCloud, replace with symlinks'")
        print("    git push origin main")
    elif log:
        write_readme(repo_root, dest_root, log)
        total_files = sum(len(e["files"]) for e in log)
        print(f"\n{'═'*60}")
        print(f"  ✅ Migration complete")
        print(f"{'═'*60}")
        print(f"  Folders migrated : {len(log)}")
        print(f"  Files moved      : {total_files}")
        print()
        print("  Next steps:")
        print("    git add org-data README_symlink.md")
        print("    git commit -m 'Migrate media files to pCloud, replace with symlinks'")
        print("    git push origin main")


if __name__ == "__main__":
    main()
