import os
from playwright.sync_api import sync_playwright

html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Kalpurush&family=Noto+Serif+Bengali:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Noto Serif Bengali', 'Kalpurush', 'SolaimanLipi', sans-serif;
            padding: 40px;
            color: #1e293b;
        }
        h1 {
            color: #0284c7;
        }
        .meta-box {
            border: 1px solid #cbd5e1;
            padding: 15px;
            border-radius: 8px;
            background: #f8fafc;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <h1>বাংলাদেশ সেনাবাহিনী বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয় (BAUST)</h1>
    <h2>ভর্তি ব্যবস্থাপনা ব্যবস্থা - পিডিএফ রিপোর্ট</h2>
    
    <div class="meta-box">
        <p><strong>আবেদনকারীর নাম:</strong> রুহুলআমিন সিদ্দিকী</p>
        <p><strong>পদবী:</strong> সহকারী সফটওয়্যার প্রকৌশলী (ICT Wing)</p>
        <p><strong>ডিপার্টমেন্ট:</strong> কম্পিউটার সায়েন্স অ্যান্ড ইঞ্জিনিয়ারিং (CSE)</p>
        <p><strong>তারিখ & সময়:</strong> ২২ জুলাই ২০২৬, ১০:৫৪ এএম</p>
    </div>
</body>
</html>
"""

out_dir = r"d:\My Drive\1-Python\1-Admission\scratch"
out_pdf = os.path.join(out_dir, "playwright_bangla_test.pdf")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content(html_content, wait_until="networkidle")
    pdf_bytes = page.pdf(format="A4", print_background=True)
    browser.close()

with open(out_pdf, "wb") as f:
    f.write(pdf_bytes)

print(f"Playwright PDF generated successfully! Size: {len(pdf_bytes)} bytes")
