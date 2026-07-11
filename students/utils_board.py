import requests
from bs4 import BeautifulSoup
import base64
import os
import re
import time
from django.conf import settings


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def is_technical_board(board_value: str) -> bool:
    """Return True if the board field indicates BTEB / Technical Education Board."""
    return 'technical' in str(board_value or '').lower()


# ---------------------------------------------------------------------------
# Existing General Board Engine  (eboardresults.com / educationboardresults.gov.bd)
# ---------------------------------------------------------------------------

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
        'Technical': 'tec',
    }

    EXAM_MAP = {
        'SSC': 'ssc',
        'HSC': 'hsc',
        'DAKHIL': 'ssc',
        'ALIM': 'hsc',
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        board_proxy = getattr(settings, 'BOARD_PROXY', None)
        if board_proxy:
            self.session.proxies = {'http': board_proxy, 'https': board_proxy}

    def get_captcha(self, use_fallback=False):
        """Fetches a fresh captcha and returns it as a base64 string."""
        target_base = self.BASE_URL_ALT if use_fallback else self.BASE_URL
        target_captcha = self.CAPTCHA_URL_ALT if use_fallback else self.CAPTCHA_URL
        try:
            headers = {
                'Referer': target_base,
                'X-Requested-With': 'XMLHttpRequest',
            }
            url = f"{target_captcha}?t={int(time.time() * 1000)}"
            has_cookie = any(cookie.name == 'human_session' for cookie in self.session.cookies)
            if has_cookie:
                response = self.session.get(url, headers=headers, timeout=5)
                if response.status_code == 200 and 'image' in response.headers.get('Content-Type', '').lower():
                    return base64.b64encode(response.content).decode('utf-8')
            r = self.session.get(target_base, timeout=10)
            from urllib.parse import urlparse
            cookie_match = re.search(r'human_session=([^;\"`\']+)', r.text)
            if cookie_match:
                cookie_value = cookie_match.group(1)
                domain = urlparse(target_base).netloc
                self.session.cookies.set('human_session', cookie_value, domain=domain)
            response = self.session.get(url, headers=headers, timeout=10)
            cookie_match = re.search(r'human_session=([^;\"`\']+)', response.text)
            if cookie_match:
                cookie_value = cookie_match.group(1)
                domain = urlparse(target_base).netloc
                self.session.cookies.set('human_session', cookie_value, domain=domain)
                response = self.session.get(url, headers=headers, timeout=10)
            if response.status_code == 200 and ('image' in response.headers.get('Content-Type', '').lower() or len(response.content) > 500):
                return base64.b64encode(response.content).decode('utf-8')
            if not use_fallback:
                return self.get_captcha(use_fallback=True)
        except Exception:
            if not use_fallback:
                return self.get_captcha(use_fallback=True)
        return None

    def fetch_result(self, exam_name, board, year, roll, reg, captcha_value):
        """Sends the verification request to the board portal."""
        p_exam = self.EXAM_MAP.get(exam_name.upper(), 'ssc')
        board_str = str(board).strip().lower()
        p_board = board_str
        for key, val in self.BOARD_MAP.items():
            if key.lower() == board_str:
                p_board = val
                break
        else:
            if 'technical' in board_str:
                p_board = 'tec'
            elif 'madrasah' in board_str:
                p_board = 'madrasah'
            else:
                for key, val in self.BOARD_MAP.items():
                    if key.lower() in board_str:
                        p_board = val
                        break

        def _clean(v):
            if v is None: return ""
            s = str(v).strip()
            if s.endswith('.0'):
                return s[:-2]
            return s

        payload = {
            'exam': p_exam,
            'year': _clean(year),
            'board': p_board,
            'result_type': '1',
            'roll': _clean(roll),
            'reg': _clean(reg),
            'captcha': str(captcha_value)
        }

        target_url = self.RESULT_URL
        target_base = self.BASE_URL
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
            print(f"VERIFY PAYLOAD: {payload}")
            response = self.session.post(target_url, data=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                return {'success': False, 'error': f"Portal Error {response.status_code}"}
            debug_path = os.path.join(settings.BASE_DIR, 'board_response_debug.html')
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            return self._parse_html_result(response.text)
        except Exception as e:
            return {'success': False, 'error': f"Connection Error: {str(e)}"}

    def _parse_html_result(self, content):
        """Parses the board's result page (handles both JSON and HTML)."""
        def grade_to_gpa(grade):
            mapping = {'A+': 5.0, 'A': 4.0, 'A-': 3.5, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
            return mapping.get(grade.upper(), 0.0)

        try:
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
                        'gender': 'Female' if res.get('sex') == '1' else 'Male',
                        'inst_name': res.get('inst_name'),
                        'group': res.get('stud_group'),
                    }
                    res_detail = res.get('res_detail', '')
                    if 'GPA=' in res_detail:
                        gpa_str = res_detail.split('GPA=')[-1].strip()
                        try:
                            parsed['gpa'] = f"{float(gpa_str):.2f}"
                        except ValueError:
                            parsed['gpa'] = gpa_str
                    elif 'PASSED' in res_detail.upper():
                        parsed['gpa'] = 'PASSED'
                    else:
                        parsed['gpa'] = res_detail
                    details = res.get('display_details', '')
                    all_subjects = {}
                    grade_map = {}
                    if details:
                        pairs = details.split(',')
                        for pair in pairs:
                            if ':' in pair:
                                parts = pair.split(':', 1)
                                grade_map[parts[0].strip()] = parts[1].strip()
                        sub_list = data_json.get('sub_details', [])
                        for sub in sub_list:
                            code = str(sub.get('SUB_CODE'))
                            name = sub.get('SUB_NAME', 'Unknown')
                            if code in grade_map:
                                all_subjects[name] = grade_map[code]
                    parsed['all_subjects'] = all_subjects
                    grades = {}
                    for code, grade in grade_map.items():
                        # General Board + Madrasah Dakhil codes (108=Math, 130=Phy, 131=Chem, 115=HM)
                        if code in ('109', '265', '108'): grades['math'] = grade_to_gpa(grade)
                        elif code in ('136', '174', '130'): grades['physics'] = grade_to_gpa(grade)
                        elif code in ('137', '176', '131'): grades['chemistry'] = grade_to_gpa(grade)
                        elif code in ('126', '115'): grades['higher_math'] = grade_to_gpa(grade)
                    parsed['grades'] = grades
                    return parsed
                elif data_json.get('msg'):
                    return {'success': False, 'error': data_json.get('msg')}
            except (ValueError, Exception):
                pass

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
                            try:
                                data['gpa'] = f"{float(value):.2f}"
                            except ValueError:
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
                        elif 'MATHEMATICS' in label:
                            data['grades']['math'] = grade_to_gpa(value)
                        elif 'PHYSICS' in label:
                            data['grades']['physics'] = grade_to_gpa(value)
                        elif 'CHEMISTRY' in label:
                            data['grades']['chemistry'] = grade_to_gpa(value)
            if 'gpa' not in data:
                return {'success': False, 'error': "Could not locate GPA in result page."}
            return data
        except Exception as e:
            return {'success': False, 'error': f"Parsing error: {str(e)}"}


# ---------------------------------------------------------------------------
# NEW: BTEB Technical Board Engine
# ---------------------------------------------------------------------------

class BTEBVerificationEngine:
    """
    Engine for verifying results from the Bangladesh Technical Education Board (BTEB)
    using the public REST API directly: POST https://result.bteb.gov.bd/api/public/result

    This bypasses all session handshakes and captcha checks entirely!
    """

    BASE_URL = "https://result.bteb.gov.bd/api/public/result"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,bn;q=0.8',
            'Connection': 'keep-alive',
        })
        board_proxy = getattr(settings, 'BOARD_PROXY', None)
        if board_proxy:
            self.session.proxies = {'http': board_proxy, 'https': board_proxy}

    def get_captcha_info(self):
        """
        Mock for general board compatibility.
        BTEB public REST API is completely automated and captcha-free.
        """
        return {
            'success': True,
            'question': 'Automated verification',
            'answer': 0,
            'mode': 'bteb',
            'captcha_image': None,
        }

    def _normalize_semester(self, curriculum_code: str, semester_val: str) -> str:
        s = str(semester_val).strip().lower()
        
        # Remove common prefixes/suffixes
        s = s.replace('semester', '').replace('class', '').replace('year', '').strip()
        s = re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', s)
        
        # Roman numerals to numbers
        roman_map = {
            'ix': '9', 'x': '10', 'xi': '11', 'xii': '12',
            'i': '1', 'ii': '2', 'iii': '3', 'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8'
        }
        if s in roman_map:
            s = roman_map[s]
            
        # Curriculum-specific mapping
        if curriculum_code in ['27', '77']:  # SSC/Dakhil (Vocational)
            if s in ['9', 'nine', 'first', '1']:
                return '1'
            if s in ['10', 'ten', 'second', '2']:
                return '2'
        elif curriculum_code in ['24', '44', '26']:  # HSC BM/Vocational
            if s in ['11', 'eleven', 'first', '1']:
                return '1'
            if s in ['12', 'twelve', 'second', '2']:
                return '2'
                
        # Fallback to only digits if present
        digits = ''.join(c for c in s if c.isdigit())
        if digits:
            return digits
            
        return semester_val

    def fetch_result(self, examination, curriculum, semester, roll, reg, exam_year=None):
        """
        Direct REST query to the public BTEB endpoint.

        Args:
            examination  : Exam type (e.g. 'SSC' or 'HSC')
            curriculum   : Curriculum code (e.g. '26' or '27')
            semester     : Semester number (e.g. '2')
            roll         : Student's board roll number
            reg          : Student's registration number
            exam_year    : The passing/exam year (e.g. '2025')

        Returns:
            Dict containing parsed student result details.
        """
        roll = self._clean(roll)
        reg  = self._clean(reg)
        curriculum_code = self._extract_curriculum_code(curriculum)
        semester = self._clean(semester)
        semester = self._normalize_semester(curriculum_code, semester)
        
        # If exam_year is missing, fallback to current year
        year = self._clean(exam_year)
        if not year:
            import datetime
            year = str(datetime.datetime.now().year)

        if not roll:
            return {'success': False, 'error': 'Roll number is required for BTEB verification.'}
        if not reg:
            return {'success': False, 'error': 'Registration number is required for BTEB verification.'}
        if not curriculum_code:
            return {'success': False, 'error': 'Curriculum is required for BTEB verification.'}
        if not semester:
            return {'success': False, 'error': 'Semester/Class is required for BTEB verification.'}

        payload = {
            "curriculumCode": curriculum_code,
            "rollNo": roll,
            "regNo": reg,
            "semester": semester,
            "examYear": year
        }

        headers = {
            'Content-Type': 'application/json',
            'Origin': 'https://result.bteb.gov.bd',
            'Referer': f'https://result.bteb.gov.bd/result-search/result?curriculum={curriculum_code}&roll={roll}&reg={reg}&semester={semester}&year={year}'
        }

        try:
            print(f"[BTEB API] Sending payload to public API: {payload}")
            resp = self.session.post(self.BASE_URL, json=payload, headers=headers, timeout=15)
            
            if resp.status_code != 200:
                return {'success': False, 'error': f"BTEB API returned error code {resp.status_code}."}

            data = resp.json()
            if not data.get('success') or not data.get('data'):
                msg = data.get('message') or "No results found for this student on BTEB portal."
                return {'success': False, 'error': msg}

            res_data = data['data']
            student_info = res_data.get('student', {})
            semesters_list = res_data.get('semesters', [])

            if not semesters_list:
                return {'success': False, 'error': 'No semester result records found.'}

            # Find matching or latest semester
            latest_sem = semesters_list[0]
            for sem in semesters_list:
                if str(sem.get('semester')) == str(semester):
                    latest_sem = sem
                    break

            gpa_info = latest_sem.get('gpa', {})
            
            # Map subjects to GPA point
            grades = {}
            for sub in latest_sem.get('subjects', []):
                sub_name = sub.get('subjectName', '').lower()
                grade_letter = sub.get('gradeLetter', '')
                
                gpa_point = 0.0
                mapping = {'A+': 5.0, 'A': 4.0, 'A-': 3.5, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
                gpa_point = mapping.get(grade_letter.upper(), 0.0)
                
                if 'math' in sub_name:
                    grades['math'] = gpa_point
                elif 'physic' in sub_name:
                    grades['physics'] = gpa_point
                elif 'chemist' in sub_name:
                    grades['chemistry'] = gpa_point

            # Populate all_subjects for details rendering in modal
            all_subjects = {}
            for sub in latest_sem.get('subjects', []):
                sub_name = sub.get('subjectName', '')
                grade_letter = sub.get('gradeLetter', '')
                if sub_name and grade_letter:
                    all_subjects[sub_name] = grade_letter

            for sub in latest_sem.get('optionalSubjects', []):
                sub_name = sub.get('subjectName', '')
                grade_letter = sub.get('gradeLetter', '')
                if sub_name and grade_letter:
                    all_subjects[sub_name] = grade_letter

            return {
                'success': True,
                'name': student_info.get('studentName', ''),
                'father_name': student_info.get('fatherName', ''),
                'mother_name': student_info.get('motherName', ''),
                'gpa': gpa_info.get('cgpa') or gpa_info.get('gpaWithOptional') or gpa_info.get('gpa', '0.00'),
                'result_text': gpa_info.get('status', 'P'),
                'inst_name': student_info.get('registeredInstitute', {}).get('name') or latest_sem.get('institute', {}).get('name', ''),
                'roll': student_info.get('studentRoll', roll),
                'reg': student_info.get('regNo', reg),
                'curriculum': student_info.get('curriculum', {}).get('name', ''),
                'semester': latest_sem.get('semester', semester),
                'exam_year': latest_sem.get('meta', {}).get('examYear', year),
                'grades': grades,
                'all_subjects': all_subjects
            }

        except Exception as e:
            return {'success': False, 'error': f"Failed to retrieve data from BTEB: {str(e)}"}

    def _extract_curriculum_code(self, curriculum: str) -> str:
        """Extract numeric code from '27 - SSC (Vocational)' → '27'."""
        if not curriculum:
            return ''
        m = re.match(r'^(\d+)', str(curriculum).strip())
        return m.group(1) if m else str(curriculum).strip()

    @staticmethod
    def _clean(value) -> str:
        """Strip whitespace and remove trailing .0 from numeric strings."""
        if value is None:
            return ''
        s = str(value).strip()
        if s.endswith('.0'):
            s = s[:-2]
        return s

