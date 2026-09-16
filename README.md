# Cloud Git File Auto-Updater

A **zero-infrastructure** GitHub automation project.

- **No server.** No VPS. No Docker. No database. No website.
- **100 % cloud.** GitHub Actions runs the update every **2 hours**, even when your laptop is off.
- **One-time setup.** Configure once, forget forever.

---

## How It Works

```
GitHub Actions triggers (every 2 hours)
          ↓
Checkout this automation repo (contains sources/)
          ↓
Run update.py
          ↓
Clone target repo (working_project)
          ↓
Copy sources/ files → target repo
          ↓
git diff — any real changes?
   Yes → commit + push
   No  → skip (already up to date)
          ↓
Workflow finishes
          ↓
Repeat in 2 hours
```

---

## Project Structure

```
git-cloud-auto-updater/
│
├── .github/
│   └── workflows/
│       └── scheduled-update.yml   ← GitHub Actions workflow (cron every 2 h)
│
├── sources/                       ← Your source files (committed here)
│   ├── main.py                    ← Pushed → working_project/main.py
│   ├── README.md                  ← Pushed → working_project/README.md
│   └── requirements.txt           ← Pushed → working_project/requirements.txt
│
├── config.json                    ← File mappings & repo settings
├── update.py                      ← Core update logic (Python)
├── README.md                      ← This file
└── .gitignore
```

### File Descriptions

| File | Purpose |
|------|---------|
| `.github/workflows/scheduled-update.yml` | Declares the cron schedule and the steps GitHub runs in the cloud |
| `sources/` | Stores the files you want to keep synced into `working_project` |
| `config.json` | Maps each source file to its target path; sets repo URL, branch, commit message |
| `update.py` | Python script that clones the target repo, copies files, detects changes, commits and pushes |
| `.gitignore` | Keeps runtime junk and secrets out of git |

---

## One-Time Setup (do this once)

### Step 1 — Create a GitHub Personal Access Token (PAT)

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens** (or classic tokens).
2. Create a token with **`Contents: Read and Write`** permission on the `working_project` repository.
3. Copy the token — you will NOT see it again.

### Step 2 — Create a NEW GitHub repository for this automation project

Create a **new empty repo** (e.g. `git-cloud-auto-updater`) on your GitHub account.

### Step 3 — Add Secrets to the automation repo

In the **automation repo** (not working_project):

```
Settings → Secrets and variables → Actions → New repository secret
```

Add these three secrets:

| Secret Name | Value |
|-------------|-------|
| `GH_PAT`   | The Personal Access Token you created in Step 1 |
| `GH_USER`  | Your GitHub username (e.g. `Nagendda`) |
| `GH_EMAIL` | Your GitHub email address |

### Step 4 — Push this project to GitHub

```bash
cd "E:\git file update\git-cloud-auto-updater"
git init
git add .
git commit -m "Initial setup: cloud auto-updater"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/git-cloud-auto-updater.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

### Step 5 — Enable Actions (if prompted)

Open the **Actions** tab of your automation repo and click **"I understand my workflows, go ahead and enable them"** if GitHub asks.

### Step 6 — Test manually

Click **Actions → Scheduled Repository Update → Run workflow** to trigger a manual run immediately and verify it works before waiting for the cron.

---

## Schedule

The workflow runs **every 2 hours** (GitHub Actions cron):

```yaml
- cron: "0 */2 * * *"
```

To change the interval, edit `.github/workflows/scheduled-update.yml`.

---

## Updating Source Files

When your source files in `E:\dynamic-memory-ai\` change:

1. Copy the updated files into `sources/`:
   ```
   copy "E:\dynamic-memory-ai\main.py"         sources\main.py
   copy "E:\dynamic-memory-ai\README.md"        sources\README.md
   copy "E:\dynamic-memory-ai\requirements.txt" sources\requirements.txt
   ```
2. Commit and push to this automation repo:
   ```bash
   git add sources/
   git commit -m "Update source files"
   git push
   ```
3. GitHub Actions will pick up the new files on the next scheduled run.

---

## Security Notes

- **No secrets in this repo.** Tokens are stored only as GitHub Actions secrets.
- The `GH_PAT` is injected via environment variable at runtime and never logged.
- The `_target_repo/` runtime clone directory is git-ignored.

---

## Target Repository

**`https://github.com/Nagendda/working_project`**

| Source file (in this repo) | Target file (in working_project) |
|---------------------------|----------------------------------|
| `sources/main.py`         | `main.py`                        |
| `sources/README.md`       | `README.md`                      |
| `sources/requirements.txt`| `requirements.txt`               |
