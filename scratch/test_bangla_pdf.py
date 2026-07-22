import os
from io import BytesIO
import xhtml2pdf.pisa as pisa

html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
</head>
<body>
    <h1>BAUST Admission System PDF Test</h1>
    <p>বাংলাদেশ সেনাবাহিনী বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয় (BAUST)</p>
    <p>আবেদনকারীর নাম: রুহুলআমিন সিদ্দিকী</p>
    <p>তারিখ: ২২ জুলাই ২০২৬, ১০:৫৪ এএম</p>
</body>
</html>
"""

result = BytesIO()
pdf = pisa.pisaDocument(BytesIO(html_content.encode("utf-8")), result)

out_dir = r"d:\My Drive\1-Python\1-Admission\scratch"
os.makedirs(out_dir, exist_ok=True)
out_file = os.path.join(out_dir, "test_output.pdf")
with open(out_file, "wb") as f:
    f.write(result.getvalue())

print(f"Generated PDF size: {len(result.getvalue())} bytes. Err: {pdf.err}")
