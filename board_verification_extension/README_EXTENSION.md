# How to Install the Custom Chrome / Edge Extension

This folder contains a ready-to-use **Manifest V3 Browser Extension** that automatically injects a **⚡ Admission System Verifier** toolbar directly onto `eboardresults.com`.

---

## 30-Second Setup Instructions:

1. **Open Extension Page in Browser**:
   - In **Google Chrome**: Go to `chrome://extensions`
   - In **Microsoft Edge**: Go to `edge://extensions`

2. **Enable Developer Mode**:
   - Turn ON the **"Developer mode"** toggle switch in the top right corner.

3. **Load Unpacked Extension**:
   - Click the **"Load unpacked"** button in the top left.
   - Select the folder: `scratch/board_verification_extension` (or extract it anywhere on your PC).

---

## How It Works:

1. Whenever you open `eboardresults.com`, a floating badge **"⚡ Admission Verifier"** appears in the top right corner.
2. **Auto-Fill**: Click **⚡ Auto-Fill Form from Clipboard** to automatically fill Examination, Board, Year, Roll, and Registration Number.
3. **Auto-Sync**: Once you solve the captcha and view the result, click **🚀 Sync Result to Admission System**. It auto-detects the Student ID, parses GPA, Name, Parents' Names, DOB, Gender, and Subject Grades, and updates your server in 1 second!
