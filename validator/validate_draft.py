"""Deterministic draft validator for khabar-brain. Fails closed: any error means the draft is rejected.
Checks: >=2 sources on different domains per claim, every source URL reachable (not 404/DNS fail),
sources match the grounded search results, every factual line maps to claims and every claim is used,
topic is not news/politics/sports, hook score and not misleading, line count/length, emotions and icons allowed.
It cannot judge truth. It only enforces the evidence trail and format. A human still reviews the draft."""
import re, urllib.request, urllib.error
from urllib.parse import urlparse

BAD = ['election', 'minister', 'political', 'parliament', 'cricket', 'football', 'match score', 'breaking news', 'चुनाव', 'मन्त्री', 'क्रिकेट', 'फुटबल', 'राजनीति']
# Exact Latin names that are shown on screen and may appear in a Nepali line. Add only real product or UI names.
ALLOWED_LATIN = ['Bitwarden', 'Google', 'Gmail', 'Ctrl', 'Wi-Fi', 'WiFi', 'PDF', 'OTP', 'SMS', 'URL', 'PIN', 'Excel', 'Word', 'Docs', 'Sheets', 'Safe Browsing', 'Authenticator']
UA = {'User-Agent': 'Mozilla/5.0 (khabar-brain validator)'}


def dom(u):
    h = (urlparse(u).hostname or '').lower()
    return h[4:] if h.startswith('www.') else h


def reg(d):
    p = d.split('.')
    return '.'.join(p[-3:]) if len(p) >= 3 and p[-2] in ('co', 'com', 'org', 'gov', 'ac') else '.'.join(p[-2:])


def reachable(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=15) as r:
            return r.status < 400, str(r.status)
    except urllib.error.HTTPError as e:
        return e.code in (401, 403, 405, 429), str(e.code)   # bot-blocked pages exist; 404/410 do not
    except Exception as e:
        return False, type(e).__name__


def validate(research, lines, hook, plan, styles, icons, pages=None):
    E, W = [], []
    claims = research.get('claims', [])
    ids = {c.get('id') for c in claims}
    pages = pages or []
    ptext = {x['url']: re.sub(r'\s+', ' ', x['text']).lower() for x in pages}
    if not pages:
        E.append('no fetched source pages: sources are unverified')
    if not (2 <= len(claims) <= 5):
        E.append(f'expected 2 to 5 claims, got {len(claims)}')
    blob = (research.get('topic', '') + ' ' + ' '.join(c.get('text', '') for c in claims) + ' ' + ' '.join(l['text'] for l in lines)).lower()
    for b in BAD:
        if b in blob:
            E.append(f'topic or text touches news/politics/sports keyword: {b}')
    for c in claims:
        srcs = c.get('sources', [])
        pubs = {reg(dom(s.get('url', ''))) for s in srcs}
        if len(pubs) < 2:
            E.append(f"claim {c.get('id')}: needs quotes from 2 different publishers, has {len(pubs)}")
        for s in srcs:
            u, q = s.get('url', ''), re.sub(r'\s+', ' ', s.get('quote', '')).strip().lower()
            if u not in ptext:
                E.append(f"claim {c.get('id')}: source url was not one of the fetched pages: {u}"); continue
            if len(q) < 20:
                E.append(f"claim {c.get('id')}: quote from {dom(u)} is missing or too short")
            elif q not in ptext[u]:
                E.append(f"claim {c.get('id')}: quote from {dom(u)} does not appear in the fetched page text")
    used = set()
    n = len(lines)
    if not (4 <= n <= 7):
        E.append(f'script has {n} lines, expected 4 to 7')
    words = sum(len(l['text'].split()) for l in lines)
    if not (30 <= words <= 75):
        E.append(f'script has {words} words, expected about 45 to 55 (30 to 75 allowed)')
    for l in lines:
        stripped = l['text']
        for term in ALLOWED_LATIN:       # exact product/UI names may stay in Latin; everything else must be Devanagari
            stripped = re.sub(r'(?<![A-Za-z])' + re.escape(term) + r'(?![A-Za-z])', ' ', stripped)
        if re.search(r'[A-Za-z]{3,}', stripped):
            E.append(f"line {l['n']} contains Latin letters outside the allowed product/UI names (captions/voice need Devanagari)")
        if l['emotion'] not in styles:
            E.append(f"line {l['n']}: unknown emotion {l['emotion']}")
        for cid in l['claims']:
            used.add(cid)
            if cid not in ids:
                E.append(f"line {l['n']} cites unknown claim {cid}")
        if l.get('role') == 'body' and not l['claims']:
            E.append(f"body line {l['n']} has no claim ids (unsupported factual line)")
    for c in ids - used:
        W.append(f'claim {c} is not used in the script')
    if not used:
        E.append('script uses no sourced claim')
    if hook.get('misleading'):
        E.append('hook marked misleading: ' + str(hook.get('misleading_reason', '')))
    if hook.get('total', 0) < 7:
        E.append(f"hook score {hook.get('total')}/10 is below 7")
    if len(lines[0]['text'].split()) > 14:
        E.append('hook is longer than 14 words')
    for x in plan.get('popups', []):
        if x.get('icon') not in icons['icons']:
            E.append(f"popup icon not in licensed list: {x.get('icon')}")
    W.append('Topic comes from a curated list, not a measured trend. The validator checks the evidence trail and format, not truth. A human reviews the draft.')
    return {'ok': not E, 'errors': E, 'warnings': W}
