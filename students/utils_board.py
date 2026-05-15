import requests
from bs4 import BeautifulSoup
import base64
import os
import time
from django.conf import settings

class BoardVerificationEngine:
    """
    Intelligent engine for communicating with eboardresults.com (V2).
    Handles session state, captcha retrieval, and result parsing.
    """
    
    BASE_URL = "https://eboardresults.com/v2/home"
    CAPTCHA_URL = "https://eboardresults.com/v2/captcha"
    RESULT_URL = "https://eboardresults.com/v2/getres"

    # Fallback Portal (Official Government V2)
    BASE_URL_ALT = "https://educationboardresults.gov.bd/v2/home"
    CAPTCHA_URL_ALT = "https://educationboardresults.gov.bd/v2/captcha"
    RESULT_URL_ALT = "https://educationboardresults.gov.bd/v2/getres"

    # Exact mappings from the portal's dropdowns
    BOARD_MAP = {
        'Dhaka': 'dhaka',
        'Barisal': 'barisal',
        'Chittagong': 'chittagong',
        'Comilla': 'comilla',
        'Dinajpur': 'dinajpur',
        'Jessore': 'jessore',
        'Jashore': 'jessore',
        'Madrasah': 'madrasah',
        'Mymensingh': 'mymensingh',
        'Rajshahi': 'rajshahi',
        'Sylhet': 'sylhet',
        'Technical': 'technical',
    }

    EXAM_MAP = {
        'SSC': 'ssc',
        'HSC': 'hsc',
        'DAKHIL': 'ssc', # Usually grouped under SSC on portal
        'ALIM': 'hsc',   # Usually grouped under HSC on portal
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })

    def get_captcha(self, use_fallback=False):
        """Fetches a fresh captcha and returns it as a base64 string."""
        target_base = self.BASE_URL_ALT if use_fallback else self.BASE_URL
        target_captcha = self.CAPTCHA_URL_ALT if use_fallback else self.CAPTCHA_URL
        
        try:
            # Step 1: Visit home page to get session cookie
            self.session.get(target_base, timeout=10)
            
            # Step 2: Artificial delay
            time.sleep(1)
            
            # Step 3: Fetch captcha with timestamp as seen in portal
            headers = {
                'Referer': target_base,
                'X-Requested-With': 'XMLHttpRequest',
            }
            url = f"{target_captcha}?t={int(time.time() * 1000)}"
            response = self.session.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200 and ('image' in response.headers.get('Content-Type', '').lower() or len(response.content) > 500):
                return base64.b64encode(response.content).decode('utf-8')
            
            # Auto-fallback
            if not use_fallback:
                return self.get_captcha(use_fallback=True)
                
        except Exception as e:
            if not use_fallback:
                return self.get_captcha(use_fallback=True)
        return None

    def fetch_result(self, exam_name, board, year, roll, reg, captcha_value):
        """
        Sends the verification request to the board portal.
        """
        p_exam = self.EXAM_MAP.get(exam_name.upper(), 'ssc')
        p_board = self.BOARD_MAP.get(board, board.lower())
        
        def _clean(v):
            if v is None: return ""
            s = str(v).strip()
            if s.endswith('.0'):
                return s[:-2]
            return s

        # Exact payload structure from browser analysis
        payload = {
            'exam': p_exam,
            'year': _clean(year),
            'board': p_board,
            'result_type': '1',
            'roll': _clean(roll),
            'reg': _clean(reg),
            'captcha': str(captcha_value)
        }

        # Determine which portal to use based on the current session cookies
        target_url = self.RESULT_URL
        target_base = self.BASE_URL
        
        # Check if we are in fallback session (more robust check)
        is_fallback = False
        for cookie in self.session.cookies:
            if "educationboardresults.gov.bd" in cookie.domain:
                is_fallback = True
                break
                
        if is_fallback:
            target_url = self.RESULT_URL_ALT
            target_base = self.BASE_URL_ALT

        headers = {
            'Referer': target_base,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }

        try:
            # DEBUG: Log payload
            print(f"VERIFY PAYLOAD: {payload}")
            
            response = self.session.post(target_url, data=payload, headers=headers, timeout=15)
            
            if response.status_code != 200:
                return {'success': False, 'error': f"Portal Error {response.status_code}"}
            
            # DEBUG: Save response for inspection if needed
            debug_path = os.path.join(settings.BASE_DIR, 'board_response_debug.html')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
                
            return self._parse_html_result(response.text)
            
        except Exception as e:
            return {'success': False, 'error': f"Connection Error: {str(e)}"}

    def _parse_html_result(self, content):
        """Parses the board's result page (handles both JSON and HTML)."""
        def grade_to_gpa(grade):
            mapping = {
                'A+': 5.0, 'A': 4.0, 'A-': 3.5, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0
            }
            return mapping.get(grade.upper(), 0.0)

        try:
            # 1. Try parsing as JSON first (Modern eboardresults.com V2)
            try:
                import json
                data_json = json.loads(content)
                if data_json.get('status') == 0 and 'res' in data_json:
                    res = data_json['res']
                    parsed = {
                        'success': True,
                        'name': res.get('name'),
                        'father_name': res.get('fname'),
                        'mother_name': res.get('mname'),
                        'dob': res.get('dob'),
                        'gender': 'Female' if res.get('sex') == '1' else 'Male', # Based on Ishrat=1
                        'inst_name': res.get('inst_name'),
                        'group': res.get('stud_group'),
                    }
                    
                    # Extract GPA from res_detail (e.g., "GPA=5.00")
                    res_detail = res.get('res_detail', '')
                    if 'GPA=' in res_detail:
                        parsed['gpa'] = res_detail.split('GPA=')[-1].strip()
                    elif 'PASSED' in res_detail.upper():
                         parsed['gpa'] = 'PASSED'
                    else:
                        parsed['gpa'] = res_detail

                    # Parse All Subject Grades
                    details = res.get('display_details', '')
                    all_subjects = {}
                    if details:
                        # Extract grades from CODE:GRADE pairs
                        grade_map = {}
                        pairs = details.split(',')
                        for pair in pairs:
                            if ':' in pair:
                                code, grade = pair.split(':')
                                grade_map[code.strip()] = grade.strip()
                        
                        # Map codes to human names using sub_details if available
                        sub_list = data_json.get('sub_details', [])
                        for sub in sub_list:
                            code = str(sub.get('SUB_CODE'))
                            name = sub.get('SUB_NAME', 'Unknown')
                            if code in grade_map:
                                all_subjects[name] = grade_map[code]
                    
                    parsed['all_subjects'] = all_subjects
                    
                    # Target specific grades for the admission form
                    grades = {}
                    for code, grade in grade_map.items():
                        # Standard Codes: 109=Math, 136=Phy, 137=Chem, 126=Higher Math
                        if code == '109': grades['math'] = grade_to_gpa(grade)
                        elif code == '136': grades['physics'] = grade_to_gpa(grade)
                        elif code == '137': grades['chemistry'] = grade_to_gpa(grade)
                        elif code == '126': grades['higher_math'] = grade_to_gpa(grade)
                    
                    parsed['grades'] = grades
                    return parsed
                elif data_json.get('msg'):
                    return {'success': False, 'error': data_json.get('msg')}
            except (ValueError, json.JSONDecodeError):
                pass # Not JSON, proceed to HTML parsing

            # 2. HTML Parsing (Fallback for government portals)
            if "Invalid Captcha" in content:
                return {'success': False, 'error': "Invalid Captcha entered."}
            if "not found" in content.lower():
                return {'success': False, 'error': "Record not found on Board Portal."}

            soup = BeautifulSoup(content, 'html.parser')
            data = {'success': True, 'grades': {}}
            
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).upper()
                        value = cells[1].get_text(strip=True)
                        
                        if 'GPA' in label:
                            data['gpa'] = value
                        elif 'NAME OF STUDENT' in label or ('NAME' in label and 'FATHER' not in label and 'MOTHER' not in label):
                            data['name'] = value
                        elif 'FATHER' in label:
                            data['father_name'] = value
                        elif 'MOTHER' in label:
                            data['mother_name'] = value
                        elif 'DATE OF BIRTH' in label or 'DOB' in label:
                            data['dob'] = value
                        elif 'GENDER' in label:
                            data['gender'] = value
                        elif 'INSTITUTE' in label:
                            data['inst_name'] = value
                        
                        # Handle Subject Table (If present in HTML)
                        elif 'MATHEMATICS' in label: data['grades']['math'] = grade_to_gpa(value)
                        elif 'PHYSICS' in label: data['grades']['physics'] = grade_to_gpa(value)
                        elif 'CHEMISTRY' in label: data['grades']['chemistry'] = grade_to_gpa(value)
            
            if 'gpa' not in data:
                return {'success': False, 'error': "Could not locate GPA in result page."}
                
            return data
            
        except Exception as e:
            return {'success': False, 'error': f"Parsing error: {str(e)}"}
