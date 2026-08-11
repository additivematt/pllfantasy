---
name: uploada
description: Instructions for compiling static payloads, committing files with git, and deploying updates to GitHub Pages for offline mobile cache updates.
---

# How to Upload PLL Fantasy Updates to GitHub (uploada)

This guide provides simple, step-by-step instructions on how to push your latest lacrosse stats and predictions from your PC to GitHub Pages. 

By updating GitHub, your phone, tablet, and other mobile devices will automatically download and cache the fresh data so they can run fully offline on game day!

---

## ⚡ Static Compilation and Pushing Updates

### When is compilation automatic?
- **Phase 3 (Post-Game stats update)**: When you run `combine_datasets.py`, it automatically calls `extract_trial_data.py` which triggers `07_prepare_static_data.py` behind the scenes. Your local files for both `interrogata` and `predicta` are updated instantly.

### When is manual compilation required?
- **Phase 2 (Game-Day Lock predictions update)**: When running prediction and simulation generation (`02_predict_probabilities.py`, `04_simulate_monte_carlo.py`, `05_bake_mc_ev.py`), the automatic fetch sequence is not triggered. You **must manually run** the compiler to update the UI data:
  ```bash
  python 07_prepare_static_data.py
  ```

### Step: Push the Updates to GitHub

> [!IMPORTANT]
> **Explain Solution & Request Permission Before Committing/Pushing**: AI agents MUST ALWAYS clearly explain the root cause, proposed solution, or intended implementation to the user FIRST and ask for permission before executing git commands to stage, commit, or push updates to GitHub, UNLESS explicitly instructed within the current chat to proceed straight away.

Choose **one** of the methods below to push the files online:

#### Option A: Using the GitHub Desktop App (Recommended for General Use)
If you have the **GitHub Desktop** app installed, updating takes 5 seconds:
1. Open **GitHub Desktop**. It will automatically detect all modified files.
2. In the bottom-left box, type a short message (e.g., `Update week 2 predictions & stats`).
3. Click the blue **"Commit to main"** (or `master`) button.
4. Click **"Push origin"** at the top.
5. **Done!** GitHub Pages will build the update in about 30 seconds.

#### Option B: Using the GitHub Web Interface (Direct in Browser)
If you don't use the Desktop app, you can update files directly on the GitHub website:

1. Open your web browser and go to your GitHub repository:
   `https://github.com/additivematt/pllfantasy`
2. **Update Interrogata Stats**:
   - Click on the `interrogata` folder.
   - Click **Add file** (top right) -> **Upload files**.
   - Drag and drop your local `all_players_stats.json` from the `interrogata` folder into the browser.
   - Scroll down and click the green **Commit changes** button.
3. **Update Predicta Weekly Predictions**:
   - Go back to the main repository screen, then click on `predicta` -> `predictions`.
   - If it is a new week (e.g., Week 2 in 2026):
     - Click **Add file** -> **Upload files**.
     - Drag and drop the `available` index file and the newly generated week file (found inside `predicta/predictions/2026/2/`) into the browser. 
     - *Note: GitHub Web lets you drag folders too, so you can simply drag the new `2026` folder and the `available` file into the upload box!*
   - Scroll down and click the green **Commit changes** button.

#### Option C: Using the Terminal (Fastest 💻)
If you have Git configured globally on your system, you can run all updates directly from the command line in 5 seconds:

1. Open **PowerShell** or your command prompt in your `scripts` folder.
2. Run the following three commands in sequence:
   ```powershell
   # 1. Stage the modified data files
   git add interrogata/all_players_stats.json predicta/predictions/
   
   # 2. Create the commit locally
   git commit -m "Update predictions & stats"
   
   # 3. Push to GitHub
   git push origin main
   ```

---

## 📱 How to Pull the Latest Data onto your Phone or Tablet

Your mobile devices use **Service Workers** to run lightning-fast and offline. To refresh their local caches with the new data:

1. **Connect to the Internet** on your phone/tablet.
2. Open your public dashboard links:
   * **Interrogata**: [https://additivematt.github.io/pllfantasy/interrogata/](https://additivematt.github.io/pllfantasy/interrogata/)
   * **Predicta**: [https://additivematt.github.io/pllfantasy/predicta/](https://additivematt.github.io/pllfantasy/predicta/)
3. **Wait 2 Seconds**:
   * **Interrogata** will show a green **`⚡ DATA UPDATED`** status pill in the top-right header once the new stats are cached.
   * **Predicta** will show a green **`🟢 ONLINE`** pill, and will immediately pre-cache all newly uploaded weeks behind the scenes.
4. **Go Offline**: You can now turn off Wi-Fi or Cellular! The dashboards are fully primed and ready for offline use on the couch or at the game.

---

## 🛠️ Troubleshooting

> [!WARNING]
> **Mobile Browser blocks registration ("Not secure")**
> * Service Workers (which enable offline mode) **strictly require** a secure connection (`https://`). 
> * Make sure you are accessing the apps via your public `https://additivematt.github.io/pllfantasy/...` links on your mobile device. If you try to open them via a local IP address (like `http://192.168.1.100:8000`), the browser will refuse to let them run offline.

> [!TIP]
> **Changes aren't showing up on my phone**
> * Force a hard-refresh on your browser.
> * On iOS Safari: Go to *Settings -> Safari -> Advanced -> Website Data*, swipe left on your GitHub Pages site, and tap *Delete*. Then reload the page.
> * On Android Chrome: Tap the three dots -> *Info (i) icon* -> *Site Settings* -> *Clear & Reset*, then reload.

---

> [!NOTE]
> All improvement ideas are tracked centrally in the [improva](../improva/SKILL.md) skill. Do not add new improvement ideas to this file.
