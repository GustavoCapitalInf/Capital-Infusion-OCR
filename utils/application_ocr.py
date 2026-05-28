"""
utils/application_ocr.py  — v3
Table-based, section-aware extraction using pdfplumber.

Architecture
------------
1. Extract the main form table from page 0 with pdfplumber.extract_tables()
2. Locate section-header rows (BUSINESS / OWNER / PROPERTY) by index
3. For every non-None cell in every row, split on the FIRST colon:
       label = text before colon
       value = text after colon  (None when blank)
4. Validate the value — reject anything that looks like a label or is empty
5. Map (section, label_lower) → field key using per-section lookup tables
6. Post-process: normalise phone/state/date/SSN/EIN, compute derived fields
"""

import io
import re
from datetime import datetime

import pdfplumber


# ─── US state normalization ────────────────────────────────────────────────────

_US_STATES = frozenset([
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN',
    'IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV',
    'NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN',
    'TX','UT','VT','VA','WA','WV','WI','WY','DC',
])

_STATE_NAMES = {
    'alabama':'AL','alaska':'AK','arizona':'AZ','arkansas':'AR',
    'california':'CA','colorado':'CO','connecticut':'CT','delaware':'DE',
    'florida':'FL','georgia':'GA','hawaii':'HI','idaho':'ID',
    'illinois':'IL','indiana':'IN','iowa':'IA','kansas':'KS',
    'kentucky':'KY','louisiana':'LA','maine':'ME','maryland':'MD',
    'massachusetts':'MA','michigan':'MI','minnesota':'MN','mississippi':'MS',
    'missouri':'MO','montana':'MT','nebraska':'NE','nevada':'NV',
    'new hampshire':'NH','new jersey':'NJ','new mexico':'NM','new york':'NY',
    'north carolina':'NC','north dakota':'ND','ohio':'OH','oklahoma':'OK',
    'oregon':'OR','pennsylvania':'PA','rhode island':'RI','south carolina':'SC',
    'south dakota':'SD','tennessee':'TN','texas':'TX','utah':'UT',
    'vermont':'VT','virginia':'VA','washington':'WA','west virginia':'WV',
    'wisconsin':'WI','wyoming':'WY','district of columbia':'DC',
}


# ─── Section label → field key maps ───────────────────────────────────────────

_BIZ = {
    'business legal name':            'Business_Legal_Name',
    'doing business as (dba)':        'Doing_Business_As_DBA',
    'dba':                            'Doing_Business_As_DBA',
    'address':                        'Business_Address',
    'city':                           'Business_City',
    'state':                          'Business_State',
    'zip':                            'Business_Zip',
    'phone':                          'Business_Phone',
    'email':                          'Business_Email',
    'entity':                         'Entity_Type1',
    'federal tax id':                 'Federal_Tax_ID',
    'business start date (mm/yyyy)':  'Date_Current_Ownership_Started',
    'date current ownership started': 'Date_Current_Ownership_Started',
}

_PRIN = {
    'principle owner name':           'Principle_Owner_Name',
    'ownership %':                    'Principle_Ownership',
    'email':                          'Principle_Email',
    'phone':                          'Principle_Phone',
    'address':                        'Principle_Address',
    'city':                           'Principle_City',
    'state':                          'Principle_State',
    'zip':                            'Principle_Zip',
    'ssn':                            'Principle_SSN',
    'date of birth':                  'Principle_DOB',
}

_SEC = {
    'secondary owner name':           'Secondary_Owner_Name',
    'ownership %':                    'Secondary_Ownership',
    'email':                          'Secondary_Email1',
    'phone':                          'Secondary_Phone',
    'address':                        'Secondary_Address',
    'city':                           'Secondary_City',
    'state':                          'Secondary_State',
    'zip':                            'Secondary_Zip',
    'ssn':                            'Secondary_SSN',
    'date of birth':                  'Secondary_DOB',
}

_PROP = {
    'business description':                 'Industry_App',
    'annual business revenue':              'Portal_Monthly_Rev',
    'estimated fico score':                 '_fico_raw',
    'requested advance amount':             'Requested_Funding_Amount',
    'average monthly credit card volume':   'Average_Monthly_Deposits',
}

# Values that are form labels, not user data — must always be rejected
_LABEL_REJECT = re.compile(
    r'^(?:ownership\s*%?|email|city|state|zip(?:\s*code)?|ssn|'
    r'date\s+of\s+birth|dob|phone|fax|address|website|'
    r'suite(?:/floor)?|floor|landlord)\s*:?\s*$',
    re.IGNORECASE,
)

# Value contains embedded "Label:" pattern = label bleed from an adjacent cell
_LABEL_BLEED = re.compile(
    r'\b(?:ownership|email|city|state|zip|ssn|phone|address)\s*:',
    re.IGNORECASE,
)


# ─── Cell parser ──────────────────────────────────────────────────────────────

def _split_cell(cell: str) -> tuple[str, str | None] | None:
    """
    Split 'Label: Value' from a single table cell.
    Returns (label_lower, value_or_None), or None if cell has no colon.
    """
    if not cell or ':' not in cell:
        return None
    idx  = cell.index(':')
    label = cell[:idx].strip()
    value = cell[idx + 1:].strip() or None
    return (label.lower(), value) if label else None


def _validate(value: str | None) -> str | None:
    """Return None if the value is empty, a bare label, or contaminated."""
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    if v.endswith(':'):          # bare label with colon
        return None
    if _LABEL_REJECT.match(v):  # known label word(s)
        return None
    if _LABEL_BLEED.search(v):  # contains "Email:" / "City:" etc.
        return None
    return v


# ─── Value normalizers ─────────────────────────────────────────────────────────

def _norm_state(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip()
    if v.upper() in _US_STATES:
        return v.upper()
    return _STATE_NAMES.get(v.lower())   # None for invalid values like "OF"


def _norm_phone(v: str | None) -> str | None:
    if not v:
        return None
    digits = re.sub(r'\D', '', v)
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) == 10:
        return f'({digits[:3]}) {digits[3:6]}-{digits[6:]}'
    return v.strip() or None


def _norm_ssn(v: str | None) -> str | None:
    if not v:
        return None
    digits = re.sub(r'\D', '', v)
    return digits if len(digits) == 9 else None


def _norm_ein(v: str | None) -> str | None:
    if not v:
        return None
    digits = re.sub(r'\D', '', v)
    if len(digits) == 9:
        return f'{digits[:2]}-{digits[2:]}'
    return v.strip() or None


def _norm_date(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip()
    for fmt in ('%m/%d/%Y', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y', '%m/%Y', '%m-%Y'):
        try:
            return datetime.strptime(v, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return v


def _norm_pct(v: str | None) -> str | None:
    if not v:
        return None
    v = v.strip()
    return v if v.endswith('%') else v + '%'


def _norm_money(v: str | None) -> str | None:
    if not v:
        return None
    return re.sub(r'[,$]', '', v).strip() or None


# ─── Section boundary detection ────────────────────────────────────────────────

def _find_row(table: list[list], pattern: str) -> int | None:
    pat = re.compile(pattern, re.IGNORECASE)
    for i, row in enumerate(table):
        for cell in row:
            if cell and pat.search(cell.strip()):
                return i
    return None


# ─── Table extraction ─────────────────────────────────────────────────────────

def _extract_from_table(table: list[list]) -> dict:
    """
    Walk every row, assign it to BIZ / PRIN / SEC / PROP based on row index,
    then parse each non-None cell as 'Label: Value'.
    """
    raw: dict[str, str | None] = {}

    owner_row = _find_row(table, r'^OWNER INFORMATION$')
    sec_row   = _find_row(table, r'Secondary Owner Name')
    prop_row  = _find_row(table, r'^BUSINESS PROPERTY INFORMATION$')

    for row_idx, row in enumerate(table):
        # Assign section — PROP check first so rows after PROPERTY header
        # are never mis-assigned to SEC
        if prop_row is not None and row_idx > prop_row:
            section_map = _PROP
        elif owner_row is not None and row_idx > owner_row:
            if sec_row is not None and row_idx >= sec_row:
                section_map = _SEC
            else:
                section_map = _PRIN
        else:
            section_map = _BIZ

        for cell in row:
            if not cell:
                continue
            parsed = _split_cell(cell)
            if not parsed:
                continue
            label_lower, raw_value = parsed
            field_key = section_map.get(label_lower)
            if not field_key:
                continue
            value = _validate(raw_value)
            # First non-null write wins; null writes only if key not yet seen
            if field_key not in raw or (raw[field_key] is None and value is not None):
                raw[field_key] = value

    return raw


# ─── Post-processing ───────────────────────────────────────────────────────────

def _post_process(raw: dict) -> dict:
    out: dict = {}

    def g(k: str) -> str | None:
        return raw.get(k)

    # Business
    out['Business_Legal_Name']            = g('Business_Legal_Name')
    out['Doing_Business_As_DBA']          = g('Doing_Business_As_DBA')
    out['Federal_Tax_ID']                 = _norm_ein(g('Federal_Tax_ID'))
    out['Entity_Type1']                   = g('Entity_Type1')
    out['Business_Address']               = g('Business_Address')
    out['Business_City']                  = g('Business_City')
    out['Business_State']                 = _norm_state(g('Business_State'))
    out['Business_Zip']                   = g('Business_Zip')
    out['Business_Phone']                 = _norm_phone(g('Business_Phone'))
    out['Business_Email']                 = g('Business_Email')
    out['Date_Current_Ownership_Started'] = g('Date_Current_Ownership_Started')
    out['Industry_App']                   = g('Industry_App')

    # Time in business — derive from start date year
    tib   = None
    start = g('Date_Current_Ownership_Started')
    if start:
        m = re.search(r'(\d{4})', start)
        if m:
            try:
                tib = datetime.now().year - int(m.group(1))
            except Exception:
                pass
    out['Time_in_Business'] = tib

    # Principle owner
    out['Principle_Owner_Name'] = g('Principle_Owner_Name')
    out['Principle_SSN']        = _norm_ssn(g('Principle_SSN'))
    out['Principle_DOB']        = _norm_date(g('Principle_DOB'))
    out['Principle_Ownership']  = _norm_pct(g('Principle_Ownership'))
    out['Principle_Email']      = g('Principle_Email')
    out['Principle_Phone']      = _norm_phone(g('Principle_Phone'))
    out['Principle_Address']    = g('Principle_Address')
    out['Principle_City']       = g('Principle_City')
    out['Principle_State']      = _norm_state(g('Principle_State'))
    out['Principle_Zip']        = g('Principle_Zip')

    # Secondary owner — all None when section was blank
    out['Secondary_Owner_Name'] = g('Secondary_Owner_Name')
    out['Secondary_SSN']        = _norm_ssn(g('Secondary_SSN'))
    out['Secondary_DOB']        = _norm_date(g('Secondary_DOB'))
    out['Secondary_Ownership']  = _norm_pct(g('Secondary_Ownership'))
    out['Secondary_Email1']     = g('Secondary_Email1')
    out['Secondary_Phone']      = _norm_phone(g('Secondary_Phone'))
    out['Secondary_Address']    = g('Secondary_Address')
    out['Secondary_City']       = g('Secondary_City')
    out['Secondary_State']      = _norm_state(g('Secondary_State'))
    out['Secondary_Zip']        = g('Secondary_Zip')

    # Funding
    out['Requested_Funding_Amount'] = _norm_money(g('Requested_Funding_Amount'))
    out['Portal_Monthly_Rev']       = _norm_money(g('Portal_Monthly_Rev'))
    out['Average_Monthly_Deposits'] = _norm_money(g('Average_Monthly_Deposits'))
    out['Percent_Ownership']        = out['Principle_Ownership']

    # Portal overrides
    out['Portal_Email']  = out['Principle_Email']  or out['Business_Email']
    out['Portal_Mobile'] = out['Principle_Phone']  or out['Business_Phone']

    # Legacy aliases (backward compatibility)
    fico_raw = g('_fico_raw')
    out['business_description']   = out['Industry_App']
    out['estimated_fico_score']   = int(fico_raw) if fico_raw and fico_raw.isdigit() else None
    out['ownership_percentage']   = out['Principle_Ownership']
    out['time_in_business_years'] = out['Time_in_Business']
    out['business_state']         = out['Business_State']
    out['business_zip']           = out['Business_Zip']

    return out


# ─── Entry point ──────────────────────────────────────────────────────────────

def parse_signed_application(pdf_input) -> dict:
    """
    Main entry point. Accepts bytes or a file-like object.
    Uses table extraction on page 0; returns all parsed fields.
    """
    if isinstance(pdf_input, bytes):
        source = io.BytesIO(pdf_input)
    else:
        pdf_input.seek(0)
        source = pdf_input

    try:
        with pdfplumber.open(source) as pdf:
            if not pdf.pages:
                return {'error': 'PDF has no pages'}
            tables = pdf.pages[0].extract_tables()
    except Exception as exc:
        return {'error': str(exc)}

    if not tables:
        return {'error': 'No tables found on page 0'}

    main_table = max(tables, key=len)
    raw        = _extract_from_table(main_table)
    return _post_process(raw)


# ─── Legacy shim ──────────────────────────────────────────────────────────────

def parse_application_text(text: str) -> dict:
    """Kept for callers that pass raw text. Returns a minimal field set."""
    def _f(pat):
        m = re.search(pat, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    return {
        'Business_Legal_Name':  _f(r'Business Legal Name\s*:\s*(.+?)(?:\s{2,}|DBA|$)'),
        'Federal_Tax_ID':       _f(r'Federal Tax ID\s*:\s*([\d\-]{8,12})'),
        'Industry_App':         _f(r'Business Description\s*:\s*(.+?)(?:\s{2,}|Annual|$)'),
        'estimated_fico_score': int(_f(r'Estimated Fico Score\s*:\s*(\d+)') or 0) or None,
        'business_state':       _f(r'\bState\s*:\s*([A-Z]{2})\b'),
        'business_zip':         _f(r'\bZip\s*:\s*(\d{5})'),
    }
