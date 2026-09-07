---
name: uploada
description: >-
  Handles git deployments to GitHub Pages and manages mobile Service Worker offline cache refreshing.
  Use this skill when deploying static UI payloads, staging git commits, or verifying offline mobile
  dashboard caching. Do NOT use for generating predictions or modifying backend models.
---

> [!IMPORTANT]
> **Skill Naming Convention**: This skill is named **uploada**. In chat responses, explanations, and documentation links, ALWAYS refer to it simply as `uploada` (or [`uploada`](file://...)). NEVER output `SKILL.md` or `uploada/SKILL.md`.

# Deploying PLL Fantasy Updates to GitHub Pages (uploada)

This guide covers deploying updated lacrosse statistics, predictions, and static UI data from your local workspace to **GitHub Pages** for offline mobile access.

---

## ⚡ Static Compilation Requirements

### Phase 3 (Post-Game Stats Update): Automatic
When you run `combine_datasets.py`, it automatically calls `extract_trial_data.py` which triggers `07_prepare_static_data.py` behind the scenes. Local data for both `interrogata` and `predicta` are updated immediately.

### Phase 2 (Game-Day Lock Predictions): Manual
When running the pre-game pipeline (`02`, `04`, `05`), you **must manually compile** static UI payloads before pushing:
```bash
python 07_prepare_static_data.py --force
```

---

## 🚀 Pushing Updates to GitHub (Terminal Git Standard)

> [!IMPORTANT]
> **Explain Solution & Request Permission Before Committing/Pushing**: AI agents MUST ALWAYS clearly explain the root cause, proposed solution, or intended implementation to the user FIRST and ask for permission before executing git commands to stage, commit, or push updates to GitHub, UNLESS explicitly instructed within the current chat to proceed straight away.
>
> **Git Command Convention**: Always invoke the standard system `git` directly (never portable or bundled scratch executables).

Execute the deployment sequence in PowerShell or Bash:

```powershell
# 1. Stage modified datasets and static payloads
git add interrogata/all_players_stats.json predicta/predictions/ predicta/advisory/

# 2. Commit updates locally
git commit -m "Update week <WEEK> predictions & stats"

# 3. Push to GitHub Pages
git push origin main
```

---

## 📱 Mobile Service Worker Cache Refreshing

Mobile devices use **Service Workers** for offline operation. To update phone/tablet caches:

1. **Connect to the Internet** on the mobile device.
2. Open the public HTTPS links:
   - **Interrogata**: [https://additivematt.github.io/pllfantasy/interrogata/](https://additivematt.github.io/pllfantasy/interrogata/)
   - **Predicta**: [https://additivematt.github.io/pllfantasy/predicta/](https://additivematt.github.io/pllfantasy/predicta/)
3. **Wait 2 Seconds**:
   - **Interrogata** will display a green **`⚡ DATA UPDATED`** status pill.
   - **Predicta** will show **`🟢 ONLINE`** and pre-cache new week prediction files.
4. **Go Offline**: Turn off Wi-Fi/Cellular; dashboards are cached for offline game-day use.

---

## 🛠️ Troubleshooting

> [!WARNING]
> **Mobile Browser Blocks Service Worker ("Not Secure")**:
> Service Workers strictly require HTTPS. Always access via `https://additivematt.github.io/pllfantasy/...`. Local IP addresses (e.g. `http://192.168.1.x:8000`) will not allow offline service workers on mobile.

> [!TIP]
> **Changes Aren't Appearing on Mobile**:
> - Force a browser cache refresh.
> - **iOS Safari**: *Settings -> Safari -> Advanced -> Website Data*, swipe left on `additivematt.github.io`, tap *Delete*, and reload.
> - **Android Chrome**: *Three dots -> Info (i) -> Site Settings -> Clear & Reset*, then reload.

---

## Verification Directive
Verify git repository state:
```bash
git status --short
```
Verify that modified tracking payloads have been committed cleanly.

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improva/SKILL.md) skill. Do not add new improvement ideas to this file.
