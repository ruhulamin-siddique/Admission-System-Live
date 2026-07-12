# User & Admin Guide: BTEB Technical Board Verification

The **BTEB (Bangladesh Technical Education Board) Verification Engine** automates student result verification directly from the official BTEB portal (https://result.bteb.gov.bd/). This guide explains how to use the verification engine on different pages of the Admission System.

---

## 1. How BTEB Verification Works (The Captcha Bypass)
Unlike general education boards (Dhaka, Rajshahi, etc.) which require solving a secure visual captcha image on every query, **BTEB queries do not require a captcha**.
* Whenever you select **Technical** as the board in a verification modal, the captcha image and input field are automatically hidden.
* Behind the scenes, the engine passes a bypass token to contact BTEB directly.
* BTEB requires **Curriculum Code** and **Semester/Class Code** instead of standard fields. The system automatically prompts you for these or pre-fills them using smart defaults.

---

## 2. Page-by-Page Usage Instructions

### 📝 A. New Student Admission Page (`Add Student`)
When registering a new candidate:
1. Scroll down to the **SSC Academic Info** or **HSC Academic Info** sections.
2. Click the blue **Verify SSC** or **Verify HSC** button to open the verification modal.
3. In the modal, select **Technical** from the **Board** dropdown.
4. **Automatic Actions**:
   * The captcha field slides out of view.
   * The BTEB-specific **Curriculum Code** and **Semester/Class** inputs will slide into view.
   * **Smart Pre-filling**:
     * For **SSC level**: Curriculum defaults to `27` (SSC Vocational) and Semester defaults to `2` (Class 10).
     * For **HSC level**: Curriculum defaults to `26` (HSC Vocational) and Semester defaults to `2` (Class 12).
5. Enter the **Roll Number**, **Registration Number**, and **Year**.
6. Check or modify the Curriculum and Semester codes if the student is from a different division (e.g. `24` for Business Management).
7. Click **Check Result**.
8. If the match is successful, review the parsed name, parents' names, and GPA. Click **Apply Data** to instantly copy all credentials (including GPA, Board, Roll, Reg, Year, and BTEB codes) back to the main registration form.

---

### ✏️ B. Edit Student Profile Page (`Edit Student`)
When editing an existing student:
1. The layout operates exactly like the *Add Student* page.
2. Click **Verify SSC** or **Verify HSC** next to the academic inputs.
3. Select **Technical** as the board.
4. Check the auto-loaded default Curriculum/Semester codes, input roll/reg details if they aren't pre-filled, and click **Check Result**.
5. Click **Apply Data** to update the main form inputs before finalizing the student edit.

---

### 👤 C. Student Profile Dashboard (`Profile Page`)
When auditing or viewing an individual student's profile:
1. Open the student's profile page. 
2. In the top-right header card or under the **Academic Details** tab, click **Verify Board Result**.
3. A modal opens with the candidate's existing Roll, Reg, Board, and Year pre-filled.
4. If the board is **Technical**, the modal will automatically display the BTEB inputs:
   * If the student already has BTEB parameters saved, they will pre-load.
   * If they are missing, the modal will pre-load the smart defaults (`27`/`2` or `26`/`2`).
5. Click **Check Result** to fetch grades.
6. A comparative table shows the database record side-by-side with the official BTEB portal data (checking name, GPA, and individual subject grades).
7. Click **Finalize & Close**. The profile page updates dynamically, adding a **Verified Badge** and saving the verification event log.

---

### 🔍 D. Academic Audit Center (`Verification Hub`)
For mass auditing of pending or mismatched records:
1. Navigate to the **Academic Audit Center** page from the sidebar menu.
2. The statistics cards show how many total records, verified records, pending verifications, and GPA mismatches exist.
3. Use the search bar and board filter dropdown to filter the queue (e.g. select **Technical** to audit all BTEB students).
4. For any candidate in the list, click the **Verify SSC** or **Verify HSC** button under the *Quick Audit Actions* column.
5. **Zero-Reload Verification**:
   * The modal launches inline. Run the check and click **Finalize & Update**.
   * The modal closes, the student's status badge in the table dynamically shifts to a green **Verified** status, and the verify button disappears. The page **does not reload**, allowing you to audit dozens of candidates rapidly.

---

### ⚙️ E. Bulk Board Audit Loop (`Student Directory`)
When running a queued bulk audit cycle across multiple selected students:
1. Go to the student list directory, select candidates, and launch the **Bulk Board Audit** loop.
2. When the wizard advances to a student whose board is **Technical**:
   * The captcha display area and geoblock warnings are automatically hidden.
   * The system sets the captcha value to `'BTEB'` automatically.
   * You simply click **VERIFY & CONTINUE** (no captcha entry required).
   * If BTEB parameters are missing from the student record, the backend automatically saves the smart defaults (`27` or `26` and `2`) and executes the lookup, preventing the bulk verification queue from stalling.

---

## 3. BTEB Curriculum & Semester Reference Sheet

Use these codes inside the verification modal if the student belongs to a specific technical curriculum:

| Board Exam | Technical Curriculum Name | Curriculum Code | Semester / Class Code |
| :--- | :--- | :---: | :---: |
| **SSC Level** | SSC (Vocational) | **`27`** | **`2`** (Class 10 / 2nd Sem) |
| **SSC Level** | Dakhil (Vocational - Madrasah) | **`77`** | **`2`** (Class 10 / 2nd Sem) |
| **SSC Level** | SSC Vocational (Class 9) | **`27`** | **`1`** (Class 9 / 1st Sem) |
| **HSC Level** | HSC (Vocational) | **`26`** | **`2`** (Class 12 / 2nd Sem) |
| **HSC Level** | HSC (Business Management - BM) | **`24`** | **`2`** (Class 12 / 2nd Sem) |
| **HSC Level** | HSC (Business Management & Tech - BMT) | **`44`** | **`2`** (Class 12 / 2nd Sem) |
| **Diploma** | Diploma in Engineering | **`15`** | **`1` to `8`** (Target Semester) |

---

## 4. Troubleshooting Common Errors

* **"BTEB API returned error code 400"**:
  * This happens when BTEB cannot find a candidate matching the entered Roll, Registration, Year, Curriculum, and Semester.
  * Check the **Curriculum Code** using the guide above. (e.g. Ensure BM students are using `24` or `44` instead of the vocational default `26`).
* **"Connection Failed" or "Timeout"**:
  * The official BTEB portal may experience high load during board result release weeks. Simply wait a few moments and click **Retry** inside the modal.
