"""
update.py
=========
Cloud Git File Auto-Updater — core update script.

This script is executed by GitHub Actions. It reads config.json,
clones the target repository, copies source files to their target
locations, checks for real git changes, and commits + pushes if
any changes are detected.

Environment variables required (set as GitHub Actions secrets):
    GH_PAT   — Personal Access Token with repo write access
    GH_USER  — GitHub username (e.g. Nagendda)
    GH_EMAIL — Git author email for commits
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("updater")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and stream output to the log."""
    log.info("$ %s", " ".join(str(c) for c in cmd))
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        log.info(result.stdout.strip())
    if result.stderr.strip():
        # Git writes progress to stderr — log as INFO, not ERROR
        log.info(result.stderr.strip())
    if check and result.returncode != 0:
        log.error("Command failed with exit code %d", result.returncode)
        sys.exit(result.returncode)
    return result


def load_config(config_path: Path) -> dict:
    """Load and validate config.json."""
    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)

    required_keys = ["target_repo", "branch", "commit_message", "files"]
    for key in required_keys:
        if key not in cfg:
            log.error("Missing required key in config.json: %s", key)
            sys.exit(1)

    if not cfg["files"]:
        log.error("'files' list in config.json is empty — nothing to update.")
        sys.exit(1)

    return cfg


def build_authenticated_url(repo_url: str, gh_user: str, gh_pat: str) -> str:
    """Inject credentials into the HTTPS remote URL."""
    # https://github.com/user/repo.git  →  https://user:token@github.com/user/repo.git
    if repo_url.startswith("https://"):
        return repo_url.replace("https://", f"https://{gh_user}:{gh_pat}@", 1)
    return repo_url  # SSH — no injection needed


def has_changes(repo_dir: Path) -> bool:
    """Return True when git detects uncommitted changes."""
    result = run(
        ["git", "status", "--porcelain"],
        cwd=repo_dir,
        check=False,
    )
    return bool(result.stdout.strip())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    log.info("=" * 60)
    log.info("Cloud Git File Auto-Updater — starting")
    log.info("=" * 60)

    # ── 1. Read environment variables ──────────────────────────────────────
    gh_pat   = os.environ.get("GH_PAT", "").strip()
    gh_user  = os.environ.get("GH_USER", "").strip()
    gh_email = os.environ.get("GH_EMAIL", "").strip()

    if not gh_pat:
        log.error("GH_PAT secret is not set. Aborting.")
        return 1
    if not gh_user:
        log.error("GH_USER secret is not set. Aborting.")
        return 1
    if not gh_email:
        log.error("GH_EMAIL secret is not set. Aborting.")
        return 1

    # ── 2. Load config ─────────────────────────────────────────────────────
    script_dir  = Path(__file__).parent.resolve()
    config_path = script_dir / "config.json"
    cfg         = load_config(config_path)

    target_repo    = cfg["target_repo"]
    branch         = cfg["branch"]
    commit_message = cfg["commit_message"]
    file_mappings  = cfg["files"]   # list of {"source": ..., "target": ...}

    log.info("Target repo : %s", target_repo)
    log.info("Branch      : %s", branch)
    log.info("Files       : %d mapping(s)", len(file_mappings))

    # ── 3. Clone target repository (handles empty repos too) ───────────────
    auth_url = build_authenticated_url(target_repo, gh_user, gh_pat)
    clone_dir = script_dir / "_target_repo"

    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    # Try a normal shallow clone first
    result = run(
        ["git", "clone", "--depth", "1", "--branch", branch, auth_url, str(clone_dir)],
        check=False,
    )

    if result.returncode != 0:
        log.warning("Shallow clone failed (repo may be empty). Initialising fresh repo...")
        clone_dir.mkdir(parents=True, exist_ok=True)
        run(["git", "init", str(clone_dir)])
        run(["git", "remote", "add", "origin", auth_url], cwd=clone_dir)
        # Try to fetch; if the remote is truly empty this will fail silently
        fetch = run(["git", "fetch", "--depth", "1", "origin", branch], cwd=clone_dir, check=False)
        if fetch.returncode == 0:
            run(["git", "checkout", "-b", branch, f"origin/{branch}"], cwd=clone_dir)
        else:
            # Completely empty remote — create the branch locally
            run(["git", "checkout", "-b", branch], cwd=clone_dir)
            log.info("Empty repository detected — will create first commit.")

    log.info("Repository ready at: %s", clone_dir)

    # ── 4. Configure git identity inside the cloned repo ──────────────────
    run(["git", "config", "user.name",  gh_user],  cwd=clone_dir)
    run(["git", "config", "user.email", gh_email], cwd=clone_dir)

    # ── 5. Copy source → target files ──────────────────────────────────────
    for mapping in file_mappings:
        source_rel = mapping.get("source", "").strip()
        target_rel = mapping.get("target", "").strip()

        if not source_rel or not target_rel:
            log.warning("Skipping invalid mapping: %s", mapping)
            continue

        source_path = script_dir / source_rel
        target_path = clone_dir / target_rel

        if not source_path.exists():
            log.error("Source file not found: %s", source_path)
            return 1

        # Create parent directories in target repo if needed
        target_path.parent.mkdir(parents=True, exist_ok=True)

        log.info("Copying: %s  →  %s", source_rel, target_rel)
        shutil.copy2(str(source_path), str(target_path))

    # ── 6. Check for real changes ──────────────────────────────────────────
    if not has_changes(clone_dir):
        log.info("No changes detected — repository is already up to date. Skipping commit.")
        return 0

    log.info("Changes detected — proceeding with commit and push.")

    # ── 7. Stage all changes ───────────────────────────────────────────────
    run(["git", "add", "--all"], cwd=clone_dir)

    # ── 8. Commit ──────────────────────────────────────────────────────────
    run(["git", "commit", "-m", commit_message], cwd=clone_dir)

    # ── 9. Push ────────────────────────────────────────────────────────────
    run(["git", "push", "origin", branch], cwd=clone_dir)

    log.info("=" * 60)
    log.info("Update complete — changes pushed to %s / %s", target_repo, branch)
    log.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
