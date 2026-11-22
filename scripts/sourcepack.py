"""Fetch the public pages of one source-pack topic as plain text. No Gemini, no key.
fetch_topic(entry) -> [{publisher, url, text}]. Wikipedia uses the REST summary API (JSON extract)."""
import json, re, urllib.request
from html.parser import HTMLParser

UA = {'User-Agent': 'Mozilla/5.0 (khabar-brain source pack)'}
MAXC = 7000


class T(HTMLParser):
    SKIP = {'script', 'style', 'noscript', 'nav', 'header', 'footer', 'svg', 'form', 'button'}

    def __init__(self):
        super().__init__(); self.o = []; self.d = 0

    def handle_starttag(self, t, a):
        if t in self.SKIP: self.d += 1
        if t in ('p', 'li', 'h1', 'h2', 'h3', 'br', 'div', 'tr'): self.o.append('\n')

    def handle_endtag(self, t):
        if t in self.SKIP and self.d: self.d -= 1

    def handle_data(self, s):
        if not self.d: self.o.append(s)


def norm(s):
    return re.sub(r'\s+', ' ', s).strip()


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def fetch_topic(entry):
    out = []
    for s in entry['sources']:
        raw = get(s['url'])
        if '/api/rest_v1/' in s['url']:
            d = json.loads(raw); text = norm(d.get('extract', ''))
        else:
            p = T(); p.feed(raw)
            lines = [norm(x) for x in ''.join(p.o).split('\n')]
            text = ' '.join(x for x in lines if len(x) > 40)   # keep real sentences, drop menu crumbs
        out.append({'publisher': s['publisher'], 'url': s.get('page', s['url']), 'fetched_url': s['url'], 'text': text[:MAXC]})
    return out
