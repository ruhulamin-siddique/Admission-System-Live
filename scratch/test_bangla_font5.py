import os
from io import BytesIO
import xhtml2pdf.pisa as pisa

font_path = r"C:/Windows/Fonts/kalpurush.ttf"
file_url = f"file:///{font_path}"

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        @font-face {{
            font-family: 'Kalpurush';
            src: url('{file_url}');
        }}
        body {{
            font-family: 'Kalpurush', sans-serif;
        }}
    </style>
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

out_file = r"d:\My Drive\1-Python\1-Admission\scratch\test_font_output5.pdf"
with open(out_file, "wb") as f:
    f.write(result.getvalue())

print(f"Generated font PDF size: {len(result.getvalue())} bytes. Err: {pdf.err}")
