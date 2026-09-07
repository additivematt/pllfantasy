# F2P Refresh Token Automation Setup

> **Context**: Instructions for extracting and configuring Firebase refresh tokens for automated scraping, referenced by [`weekflow`](../SKILL.md).

---

## One-Time Setup for F2P Refresh Token Automation

To run the weekly scraper (`08_scrape_challenger_rosters.py`) automatically without manual token copy-paste or HAR file exports, set up a local `.env` file with your credentials or refresh token.

### Setup Steps:
1. Copy the template `.env.example` to a new file named `.env` in the `scripts/` directory:
   ```bash
   cp .env.example .env
   ```
2. Fill in **one** of the authentication methods:
   - **Method A (Email & Password)**: If your account uses a password, enter your email and password:
     ```ini
     F2P_EMAIL=your_email@example.com
     F2P_PASSWORD=your_password
     ```
   - **Method B (Refresh Token)**: If you log in via Magic Link, extract your long-lived Firebase **Refresh Token** from your browser's IndexedDB and enter it as `F2P_REFRESH_TOKEN` in the `.env` file.

---

## Easy IndexedDB Token Extraction

1. Open your desktop browser to the logged-in [F2P leagues page](https://f2p.premierlacrosseleague.com/fantasy/leagues).
2. Open **Developer Tools** (`F12`), go to the **Console** tab.
3. Paste the following JavaScript snippet and press **Enter**:
   ```javascript
   (async function() {
     const db = await new Promise((res, rej) => {
       const req = indexedDB.open("firebaseLocalStorageDb");
       req.onsuccess = () => res(req.result);
       req.onerror = rej;
     });
     const tx = db.transaction("firebaseLocalStorage", "readonly");
     const store = tx.objectStore("firebaseLocalStorage");
     const records = await new Promise((res) => {
       const req = store.getAll();
       req.onsuccess = () => res(req.result);
     });
     if (records && records.length > 0) {
       const token = records[0].value.stsTokenManager?.refreshToken || records[0].value.refreshToken;
       console.log("Your F2P_REFRESH_TOKEN is:\n\n" + token);
     } else {
       console.error("No active session found in IndexedDB.");
     }
   })();
   ```
4. Copy the printed token and save it in your `.env` file:
   ```ini
   F2P_REFRESH_TOKEN="<COPIED_TOKEN>"
   ```
