"""
Credit card information parser — greedy full-text scanning architecture.

Extracts card number, expiry date and CVV from arbitrary messy text:
no line-break dependency, handles multiple cards in a single blob,
OCR character correction, full-width normalization, and more.
"""

import re
from typing import List, Optional, Tuple

from app.card_model import CardInfo, luhn_check, detect_brand


# ---------------------------------------------------------------------------
# A. Full-width -> half-width normalization
# ---------------------------------------------------------------------------

def _fullwidth_to_halfwidth(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        elif code == 0x3000:
            out.append(' ')
        else:
            out.append(ch)
    return ''.join(out)


# ---------------------------------------------------------------------------
# B. OCR character correction (context-aware)
# ---------------------------------------------------------------------------

_OCR_DIGIT_MAP = str.maketrans({
    'O': '0', 'o': '0',
    'Q': '0', 'C': '0',
    'l': '1', 'I': '1', '|': '1',
    'S': '5', 's': '5',
    'B': '8',
    'G': '6', 'b': '6',
    'Z': '2', 'z': '2',
    'g': '9', 'q': '9',
    'D': '0',
    'T': '7',
    'A': '4',
})


_OCR_CHARS = r'OoQClI|SsBGbZzgqDTA'

def _fix_ocr_digits(text: str) -> str:
    return re.sub(
        r'(?<=[0-9])([' + _OCR_CHARS + r'])(?=[0-9])',
        lambda m: m.group(1).translate(_OCR_DIGIT_MAP),
        text,
    )


def _fix_ocr_in_digit_groups(text: str) -> str:
    char_class = r'[0-9' + _OCR_CHARS + r']'

    def _fix_group(m):
        return m.group(0).translate(_OCR_DIGIT_MAP)

    text = re.sub(char_class + r'{13,19}', _fix_group, text)
    text = re.sub(
        char_class + r'{4}[\s\-]' + char_class + r'{4}'
        r'[\s\-]' + char_class + r'{4}[\s\-]' + char_class + r'{3,4}',
        _fix_group, text,
    )
    text = re.sub(
        char_class + r'{4,8}[\s\-]' + char_class + r'{4,8}'
        r'(?:[\s\-]' + char_class + r'{4,8})?',
        _fix_group, text,
    )
    return text


# ---------------------------------------------------------------------------
# C. Label stripping
# ---------------------------------------------------------------------------

_LABEL_PATTERNS = re.compile(
    r'(?:卡号|卡bin|card\s*(?:no\.?|number|num|#)?|号码|信用卡|\bpan\b|\bcc\b)\s*[:：=]?\s*',
    re.IGNORECASE,
)
_EXP_LABEL = re.compile(
    r'(?:有效期[至到]?|到期日?|过期日?|exp(?:iry)?(?:\s*date)?|valid\s*(?:thru|through|until|dates?)?|'
    r'日期|good\s*thru|月\s*/?\s*年)\s*[:：=]?\s*',
    re.IGNORECASE,
)
_CVV_LABEL = re.compile(
    r'(?:cvv2?|cvc2?|csv|安全码|安全代码|校验码|背面三位|'
    r'security\s*code|verification(?:\s*code)?|cvn2?)\s*[:：=]?\s*',
    re.IGNORECASE,
)


def _strip_labels(text: str) -> str:
    text = _LABEL_PATTERNS.sub(' ', text)
    text = _EXP_LABEL.sub(' ', text)
    text = _CVV_LABEL.sub(' ', text)
    return text


# ---------------------------------------------------------------------------
# D. Separator normalization
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = _fullwidth_to_halfwidth(text)
    text = text.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
    text = text.replace('\t', ' ')
    text = text.replace('|', ' ')
    text = text.replace(';', ' ')
    text = text.replace('，', ' ')
    text = text.replace(',', ' ')
    text = text.replace('。', '.')
    text = re.sub(r'[#*~·•`\[\]{}()（）《》<>]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ---------------------------------------------------------------------------
# E. Expiry extraction (multiple formats)
# ---------------------------------------------------------------------------

_PAT_YYYY_SEP_MM = re.compile(r'\b(\d{4})\s*[/\-\.]\s*(\d{2})\b')
_PAT_MM_SEP_YYYY = re.compile(r'\b(\d{2})\s*[/\-\.]\s*(\d{4})\b')
_PAT_MM_SEP_YY = re.compile(r'\b(\d{2})\s*[/\-\.]\s*(\d{2})\b')
_PAT_MMYY = re.compile(r'(?<!\d)(\d{2})(\d{2})(?!\d)')
_PAT_CN_YYYY_MM = re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月')
_PAT_CN_MM_YY = re.compile(r'(\d{1,2})\s*月\s*[/\-]?\s*(\d{2,4})\s*年?')

_MIN_YY = 18
_MAX_YYYY = 2099


def _valid_yy(yy: int) -> bool:
    return yy >= _MIN_YY


def _valid_yyyy(yyyy: int) -> bool:
    return 2000 + _MIN_YY <= yyyy <= _MAX_YYYY


def _extract_expiry_from_text(text: str) -> Optional[Tuple[str, int, int]]:
    for m in _PAT_CN_YYYY_MM.finditer(text):
        yyyy, mm = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12 and _valid_yyyy(int(yyyy)):
            return f"{int(mm):02d}/{yyyy[2:]}", m.start(), m.end()

    for m in _PAT_CN_MM_YY.finditer(text):
        mm, yr = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12:
            if len(yr) == 4 and _valid_yyyy(int(yr)):
                return f"{int(mm):02d}/{yr[2:]}", m.start(), m.end()
            elif len(yr) == 2 and _valid_yy(int(yr)):
                return f"{int(mm):02d}/{yr}", m.start(), m.end()

    for m in _PAT_YYYY_SEP_MM.finditer(text):
        yyyy, mm = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12 and _valid_yyyy(int(yyyy)):
            return f"{mm}/{yyyy[2:]}", m.start(), m.end()

    for m in _PAT_MM_SEP_YYYY.finditer(text):
        mm, yyyy = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12 and _valid_yyyy(int(yyyy)):
            return f"{mm}/{yyyy[2:]}", m.start(), m.end()

    for m in _PAT_MM_SEP_YY.finditer(text):
        mm, yy = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12 and _valid_yy(int(yy)):
            return f"{mm}/{yy}", m.start(), m.end()

    for m in _PAT_MMYY.finditer(text):
        mm, yy = m.group(1), m.group(2)
        if 1 <= int(mm) <= 12 and _valid_yy(int(yy)):
            return f"{mm}/{yy}", m.start(), m.end()

    return None


# ---------------------------------------------------------------------------
# F. Card number extraction (greedy regex + Luhn + approximate fix)
# ---------------------------------------------------------------------------

_CARD_NUM_CONTINUOUS = re.compile(r'(\d{13,19})')

_CARD_NUM_SEPARATED = re.compile(
    r'(\d{4}[\s\-\.]+\d{4}[\s\-\.]+\d{4}[\s\-\.]+\d{3,4}(?:[\s\-\.]+\d{1,3}(?!\d)(?!\s*[/\-\.]\s*\d))?)'
)

_CARD_NUM_AMEX = re.compile(
    r'(\d{4}[\s\-\.]+\d{6}[\s\-\.]+\d{5})'
)

_CARD_NUM_FLEX = re.compile(
    r'(\d{4,8}[\s\-\.]+\d{4,8}(?:[\s\-\.]+\d{4,8})?)'
)


def _extract_digits(s: str) -> str:
    return re.sub(r'[^\d]', '', s)


def _is_known_brand(digits: str) -> bool:
    return detect_brand(digits) != "unknown"


def _try_luhn_fix(digits: str) -> Optional[str]:
    if luhn_check(digits):
        return digits
    if not (13 <= len(digits) <= 19):
        return None
    nums = [int(d) for d in digits]
    n = len(nums)
    checksum = 0
    for i, d in enumerate(reversed(nums)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    remainder = checksum % 10
    if remainder == 0:
        return digits
    for i in range(n):
        pos_from_right = n - 1 - i
        old_d = nums[i]
        for new_d in range(10):
            if new_d == old_d:
                continue
            if pos_from_right % 2 == 1:
                old_contrib = old_d * 2
                if old_contrib > 9:
                    old_contrib -= 9
                new_contrib = new_d * 2
                if new_contrib > 9:
                    new_contrib -= 9
            else:
                old_contrib = old_d
                new_contrib = new_d
            if (checksum - old_contrib + new_contrib) % 10 == 0:
                return digits[:i] + str(new_d) + digits[i + 1:]
    return None


def _find_all_card_numbers(text: str) -> List[Tuple[str, int, int]]:
    candidates = []
    seen_positions = set()

    for pat in [_CARD_NUM_AMEX, _CARD_NUM_SEPARATED, _CARD_NUM_FLEX]:
        for m in pat.finditer(text):
            digits = _extract_digits(m.group(1))
            if 13 <= len(digits) <= 19:
                pos_key = (m.start(), m.end())
                if pos_key not in seen_positions:
                    seen_positions.add(pos_key)
                    candidates.append((digits, m.start(), m.end()))

    for m in _CARD_NUM_CONTINUOUS.finditer(text):
        digits = m.group(1)
        overlaps = False
        for _, s, e in candidates:
            if not (m.end() <= s or m.start() >= e):
                overlaps = True
                break
        if not overlaps:
            candidates.append((digits, m.start(), m.end()))

    results = []
    seen_numbers = set()
    for digits, start, end in candidates:
        if luhn_check(digits) and _is_known_brand(digits):
            if digits not in seen_numbers:
                seen_numbers.add(digits)
                results.append((digits, start, end))
            continue

        if luhn_check(digits):
            if digits not in seen_numbers:
                seen_numbers.add(digits)
                results.append((digits, start, end))
            continue

        if _is_known_brand(digits):
            fixed = _try_luhn_fix(digits)
            if fixed and fixed not in seen_numbers:
                seen_numbers.add(fixed)
                results.append((fixed, start, end))

    results.sort(key=lambda x: x[1])
    return results


# ---------------------------------------------------------------------------
# G. CVV extraction
# ---------------------------------------------------------------------------

def _extract_cvv_from_text(text: str) -> Optional[Tuple[str, int, int]]:
    best = None
    best_score = -1
    for m in re.finditer(r'(?<!\d)(\d{3,4})(?!\d)', text):
        val = m.group(1)
        score = 0
        if len(val) == 3:
            score += 2
        elif len(val) == 4:
            score += 1
        proximity = max(0, 20 - m.start())
        score += proximity
        if score > best_score:
            best_score = score
            best = (val, m.start(), m.end())
    return best


# ---------------------------------------------------------------------------
# H. Masked card number detection
# ---------------------------------------------------------------------------

_MASKED_PATTERN = re.compile(
    r'\b\d{4}[\s\-\.]*[*xX]{4,}[\s\-\.]*[*xX]{4,}[\s\-\.]*\d{4}\b'
)


def detect_masked_cards(text: str) -> List[str]:
    text = _fullwidth_to_halfwidth(text)
    text = _normalize(text)
    return [m.group() for m in _MASKED_PATTERN.finditer(text)]


# ---------------------------------------------------------------------------
# I. Core: Full-text greedy scan
# ---------------------------------------------------------------------------

def _greedy_scan(text: str) -> List[CardInfo]:
    card_nums = _find_all_card_numbers(text)
    if not card_nums:
        return []

    results = []
    seen = set()

    for idx, (number, num_start, num_end) in enumerate(card_nums):
        if idx + 1 < len(card_nums):
            region_end = card_nums[idx + 1][1]
        else:
            region_end = len(text)

        search_text = text[num_end:region_end]

        exp_result = _extract_expiry_from_text(search_text)
        exp_in_search = exp_result is not None
        if not exp_result:
            exp_result = _extract_expiry_from_text(text[max(0, num_start - 30):num_start])

        expiry = ""
        cvv_val = ""

        if exp_result:
            expiry, exp_start_rel, exp_end_rel = exp_result

            if exp_in_search:
                after_expiry = search_text[exp_end_rel:]
            else:
                after_expiry = search_text

            cvv_result = _extract_cvv_from_text(after_expiry)
            cvv_from_after = cvv_result is not None
            if not cvv_result:
                cvv_result = _extract_cvv_from_text(search_text)
                cvv_from_after = False

            if cvv_result:
                cvv_val = cvv_result[0]
                if cvv_val == expiry.replace('/', ''):
                    if cvv_from_after:
                        remaining = after_expiry[cvv_result[2]:]
                    else:
                        remaining = search_text[cvv_result[2]:]
                    cvv_result2 = _extract_cvv_from_text(remaining)
                    cvv_val = cvv_result2[0] if cvv_result2 else ""
        else:
            cvv_result = _extract_cvv_from_text(search_text)
            if cvv_result:
                cvv_val = cvv_result[0]

        if not expiry and not cvv_val:
            continue

        if number not in seen:
            seen.add(number)
            results.append(CardInfo(number=number, expiry=expiry, cvv=cvv_val))

    return results


# ---------------------------------------------------------------------------
# J. Legacy single-line parse (fallback)
# ---------------------------------------------------------------------------

def _parse_single_line_legacy(line: str) -> Optional[CardInfo]:
    line = _strip_labels(line)
    line = _normalize(line)
    line = _fix_ocr_digits(line)
    line = _fix_ocr_in_digit_groups(line)

    if not line:
        return None

    line = re.sub(r'(\d{4})-(\d{4})-(\d{4})-(\d{3,4})', r'\1\2\3\4', line)

    tokens = line.split()

    card_number = None
    card_idx = -1
    for i, token in enumerate(tokens):
        digits_only = re.sub(r'[\s\-\.]', '', token)
        if digits_only.isdigit() and 13 <= len(digits_only) <= 19:
            fixed = _try_luhn_fix(digits_only)
            if fixed:
                card_number = fixed
                card_idx = i
                break

    if not card_number:
        combined = ""
        start_idx = -1
        end_idx = -1
        for i, token in enumerate(tokens):
            if token.isdigit() and 2 <= len(token) <= 6:
                if start_idx == -1:
                    start_idx = i
                combined += token
                end_idx = i
            else:
                if 13 <= len(combined) <= 19:
                    fixed = _try_luhn_fix(combined)
                    if fixed:
                        card_number = fixed
                        card_idx = end_idx
                        break
                combined = ""
                start_idx = -1
                end_idx = -1
        if not card_number and 13 <= len(combined) <= 19:
            fixed = _try_luhn_fix(combined)
            if fixed:
                card_number = fixed
                card_idx = end_idx

    if not card_number:
        return None

    remaining_tokens = tokens[card_idx + 1:] if card_idx >= 0 else tokens
    remaining_text = ' '.join(remaining_tokens)

    exp_result = _extract_expiry_from_text(remaining_text)
    expiry = ""
    cvv_val = ""

    if exp_result:
        expiry = exp_result[0]
        after_exp = remaining_text[exp_result[2]:]
        cvv_result = _extract_cvv_from_text(after_exp)
        cvv_from_after = cvv_result is not None
        if not cvv_result:
            cvv_result = _extract_cvv_from_text(remaining_text)
            cvv_from_after = False
        if cvv_result:
            cvv_val = cvv_result[0]
            if cvv_val == expiry.replace('/', ''):
                if cvv_from_after:
                    rest = after_exp[cvv_result[2]:]
                else:
                    rest = remaining_text[cvv_result[2]:]
                cvv2 = _extract_cvv_from_text(rest)
                cvv_val = cvv2[0] if cvv2 else ""
    else:
        cvv_result = _extract_cvv_from_text(remaining_text)
        if cvv_result:
            cvv_val = cvv_result[0]

    if not expiry and not cvv_val:
        return None

    return CardInfo(number=card_number, expiry=expiry, cvv=cvv_val)


# ---------------------------------------------------------------------------
# K. Main entry point
# ---------------------------------------------------------------------------

def parse_text(text: str) -> List[CardInfo]:
    if not text or not text.strip():
        return []

    text = _fullwidth_to_halfwidth(text)
    text_clean = _strip_labels(text)
    text_clean = _normalize(text_clean)
    text_clean = _fix_ocr_digits(text_clean)
    text_clean = _fix_ocr_in_digit_groups(text_clean)

    results = _greedy_scan(text_clean)
    if results:
        return _deduplicate(results)

    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        card = _parse_single_line_legacy(line)
        if card:
            results.append(card)

    if not results and len(lines) > 1:
        for window in range(2, min(4, len(lines) + 1)):
            for i in range(len(lines) - window + 1):
                combined = ' '.join(lines[i:i + window])
                card = _parse_single_line_legacy(combined)
                if card and not any(c.number == card.number for c in results):
                    results.append(card)

    return _deduplicate(results) if results else []


def _deduplicate(cards: List[CardInfo]) -> List[CardInfo]:
    seen = set()
    unique = []
    for card in cards:
        key = card.number
        if key not in seen:
            seen.add(key)
            unique.append(card)
    return unique
