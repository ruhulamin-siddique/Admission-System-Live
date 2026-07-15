"""
scratch/compile_po.py
=====================
Pure Python implementation of gettext PO-to-MO compiler.
Compiles English and Bangla PO catalogs into binary MO catalogs.
Avoids gettext package command-line dependencies on Windows/production.
"""

import os
import struct
import re

def parse_po(po_path):
    """
    Parses a gettext PO file.
    Returns a list of (msgid, msgstr) tuples.
    """
    entries = []
    current_msgid = None
    current_msgstr = None
    state = None # 'msgid' or 'msgstr'

    # Regex to extract string contents inside double quotes
    str_re = re.compile(r'^\s*"(.*)"\s*$')

    def unescape(s):
        # Handle standard escape sequences
        escapes = {
            '\\n': '\n',
            '\\t': '\t',
            '\\r': '\r',
            '\\\\': '\\',
            '\\"': '"',
        }
        for esc, char in escapes.items():
            s = s.replace(esc, char)
        return s

    with open(po_path, 'r', encoding='utf-8') as f:
        for line in f:
            line_str = line.strip()
            if not line_str or line_str.startswith('#'):
                continue

            if line_str.startswith('msgid'):
                # Save previous entry if complete
                if current_msgid is not None:
                    entries.append((current_msgid, current_msgstr or ''))
                match = re.match(r'^msgid\s*"(.*)"\s*$', line_str)
                current_msgid = unescape(match.group(1)) if match else ''
                current_msgstr = None
                state = 'msgid'

            elif line_str.startswith('msgstr'):
                match = re.match(r'^msgstr\s*"(.*)"\s*$', line_str)
                current_msgstr = unescape(match.group(1)) if match else ''
                state = 'msgstr'

            elif line_str.startswith('"'):
                match = str_re.match(line_str)
                if match:
                    val = unescape(match.group(1))
                    if state == 'msgid':
                        current_msgid += val
                    elif state == 'msgstr':
                        current_msgstr += val

        # Save last entry
        if current_msgid is not None:
            entries.append((current_msgid, current_msgstr or ''))

    return entries


def compile_mo(po_path, mo_path):
    """
    Compiles parsed PO entries to a gettext binary MO file format.
    """
    print(f"Parsing: {po_path}")
    entries = parse_po(po_path)

    # Sort entries by msgid key byte-order (required by gettext format spec)
    # The header entry (msgid = "") must remain the first entry
    header_entry = None
    data_entries = []
    for msgid, msgstr in entries:
        if msgid == "":
            header_entry = (msgid, msgstr)
        else:
            data_entries.append((msgid, msgstr))

    data_entries.sort(key=lambda item: item[0].encode('utf-8'))
    
    sorted_entries = []
    if header_entry:
        sorted_entries.append(header_entry)
    sorted_entries.extend(data_entries)

    N = len(sorted_entries)
    
    # Pre-build string byte sequences
    orig_strings = [item[0].encode('utf-8') for item in sorted_entries]
    trans_strings = [item[1].encode('utf-8') for item in sorted_entries]

    # Calculate table offsets
    # Header size: 28 bytes
    # Original table size: N * 8 bytes
    # Translation table size: N * 8 bytes
    orig_table_offset = 28
    trans_table_offset = orig_table_offset + N * 8
    strings_offset = trans_table_offset + N * 8

    orig_table = []
    trans_table = []
    
    current_offset = strings_offset
    
    # Original strings metadata offsets
    for s in orig_strings:
        orig_table.append((len(s), current_offset))
        current_offset += len(s) + 1 # +1 for null terminator

    # Translation strings metadata offsets
    for s in trans_strings:
        trans_table.append((len(s), current_offset))
        current_offset += len(s) + 1

    # Write binary MO file
    print(f"Writing binary: {mo_path}")
    with open(mo_path, 'wb') as f:
        # Magic: 0x950412de, Revision: 0, Number of strings: N, 
        # Orig table offset, Trans table offset, Hash table size (0), Hash table offset (0)
        header = struct.pack(
            '<I I I I I I I',
            0x950412de, 0, N,
            orig_table_offset, trans_table_offset,
            0, 0
        )
        f.write(header)

        # Write original strings sizes and offsets
        for length, offset in orig_table:
            f.write(struct.pack('<I I', length, offset))

        # Write translation strings sizes and offsets
        for length, offset in trans_table:
            f.write(struct.pack('<I I', length, offset))

        # Write null-terminated original strings
        for s in orig_strings:
            f.write(s + b'\x00')

        # Write null-terminated translation strings
        for s in trans_strings:
            f.write(s + b'\x00')

    print("Success [OK]")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    langs = ['en', 'bn']
    for lang in langs:
        po_path = os.path.join(base_dir, 'locale', lang, 'LC_MESSAGES', 'django.po')
        mo_dir = os.path.join(base_dir, 'locale', lang, 'LC_MESSAGES')
        mo_path = os.path.join(mo_dir, 'django.mo')
        
        if os.path.exists(po_path):
            os.makedirs(mo_dir, exist_ok=True)
            compile_mo(po_path, mo_path)
        else:
            print(f"Error: PO file not found at {po_path}")
