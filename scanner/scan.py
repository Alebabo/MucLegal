"""Stateless, deterministic AGB comparison. No browser, models or evidence upload."""
import hashlib
import json
import re
import time
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, urlencode
from lxml import html
from engine.core import NormalizationConfig, normalize_html, normalize_plain_text
from engine.http import HttpFetcher, FetchPolicy, FetchFailure

ROOT = Path(__file__).resolve().parent
MARKER = re.compile(r'^(?:§\s*\d+|\(\d+\)|\d+[.)]\s|[-•]\s|Artikel\s+\d+)', re.I)

def paragraphs(text):
    """Keep legal paragraph boundaries, join PDF/HTML layout line wrapping."""
    lines = normalize_plain_text(text).splitlines()
    result, buffer = [], []
    for line in lines:
        if not line.strip():
            continue
        if MARKER.match(line) and buffer:
            result.append(' '.join(buffer)); buffer = []
        buffer.append(line.strip())
    if buffer: result.append(' '.join(buffer))
    # Non-numbered documents retain extraction paragraph boundaries.
    if len(result) <= 1 and len(lines) > 1:
        result = [line for line in lines if line.strip()]
    return result

def digest(parts):
    return hashlib.sha256('\n\n'.join(parts).encode()).hexdigest()

def tokens(before, after):
    a, b = re.findall(r'\s+|\w+|[^\w\s]', before), re.findall(r'\s+|\w+|[^\w\s]', after)
    left, right = [], []
    for op, i, j, k, l in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if i != j: left.append({'text': ''.join(a[i:j]), 'changed': op != 'equal'})
        if k != l: right.append({'text': ''.join(b[k:l]), 'changed': op != 'equal'})
    return left, right

def align_replacements(old, new):
    """Monotonic fuzzy alignment: inserted sections do not shift unrelated clauses."""
    n,m=len(old),len(new)
    if n*m>1600:
        return [(i,None) for i in range(n)]+[(None,j) for j in range(m)]
    scores=[[0.0]*(m+1) for _ in range(n+1)]
    paths={}
    for i in range(n+1):
        for j in range(m+1):
            if not i and not j: continue
            options=[]
            if i: options.append((scores[i-1][j]-.25,1,'delete'))
            if j: options.append((scores[i][j-1]-.25,0,'insert'))
            if i and j:
                # Bound fuzzy-matching cost; the rendered diff still uses the complete text.
                a,b=old[i-1],new[j-1]
                a=a if len(a)<2000 else a[:1000]+a[-1000:]
                b=b if len(b)<2000 else b[:1000]+b[-1000:]
                similarity=SequenceMatcher(None,a,b,autojunk=False).ratio()
                if similarity>=.4: options.append((scores[i-1][j-1]+2*similarity-1,2,'pair'))
            score,_,operation=max(options)
            scores[i][j]=score; paths[i,j]=operation
    aligned=[];i,j=n,m
    while i or j:
        operation=paths[i,j]
        if operation=='pair': aligned.append((i-1,j-1));i-=1;j-=1
        elif operation=='delete': aligned.append((i-1,None));i-=1
        else: aligned.append((None,j-1));j-=1
    return list(reversed(aligned))

def compare(before, after):
    rows=[]
    for op,i,j,k,l in SequenceMatcher(None,before,after,autojunk=False).get_opcodes():
        if op=='equal':
            rows.extend({'kind':'equal','left':[{'text':before[x],'changed':False}],'right':[{'text':before[x],'changed':False}],'oldNumber':x+1,'newNumber':k+x-i+1} for x in range(i,j))
            continue
        for old_index,new_index in align_replacements(before[i:j],after[k:l]):
            old=before[i+old_index] if old_index is not None else ''
            new=after[k+new_index] if new_index is not None else ''
            left,right=tokens(old,new)
            rows.append({'kind':'replace' if old and new else ('delete' if old else 'insert'),'left':left,'right':right,'oldNumber':i+old_index+1 if old_index is not None else None,'newNumber':k+new_index+1 if new_index is not None else None})
    return rows

def clean_url(value):
    value = value.strip()
    if '://' not in value: value = 'https://' + value
    parsed = urlsplit(value)
    if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,80,443):
        raise ValueError('Bitte eine öffentliche HTTP(S)-Webseite ohne Zugangsdaten eingeben.')
    if len(value) > 2048: raise ValueError('Die URL ist zu lang.')
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path or '/', parsed.query, ''))

class BoundedFetcher(HttpFetcher):
    """Limit input size and redirects while preserving the project's safety gates."""
    def __init__(self):
        super().__init__(FetchPolicy(timeout_seconds=6, max_attempts=1, require_public_network=True))
        self.redirects = 0
    def _validate_url(self, url):
        clean_url(url)
        super()._validate_url(url)
    def _decode_body(self, body, headers):
        if len(body) > 2_000_000: raise ValueError('Seite zu groß (maximal 2 MB).')
        return super()._decode_body(body,headers)
    def _require_robots_permission(self, url):
        self.redirects += 1
        if self.redirects > 9: raise ValueError('Zu viele Weiterleitungen.')
        return super()._require_robots_permission(url)

def discover(fetched):
    doc = html.fromstring(fetched.decoded_html)
    ranked = []
    for node in doc.xpath('//a[@href]'):
        label = ' '.join(node.itertext()).strip().lower()
        href = node.get('href','')
        target = urljoin(fetched.final_url, href)
        if urlsplit(target).hostname != urlsplit(fetched.final_url).hostname: continue
        if urlsplit(target).path.lower().endswith('.pdf'): continue
        score = (10 if re.search(r'\bagb\b|allgemeine geschäftsbedingungen|terms of (?:service|use|sale)|terms and conditions', label) else 0)
        score += 3 if re.search(r'agb|terms-of|terms_and|terms-and', href.lower()) else 0
        if score: ranked.append((-score, target))
    if re.search(r'agb|terms|geschaeftsbedingungen', urlsplit(fetched.final_url).path.lower()): return fetched.final_url
    return min(ranked)[1] if ranked else None

def saved_baseline(url):
    """Reuse the sourced archive fixture only for its exact current terms URL."""
    for name in ('decathlon','mueller'):
        data=json.loads((ROOT/'data'/f'{name}.json').read_text())
        if clean_url(url)==clean_url(data['url']):
            source=data['before']
            return source['text'], {k:v for k,v in source.items() if k!='text'}
    return None

def archived_baseline(url, fetcher):
    """Find the latest successful HTML snapshot before today, without inventing history."""
    cutoff=(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y%m%d235959')
    query=urlencode({'url':url,'output':'json','filter':'statuscode:200','filter!':'mimetype:text/html','to':cutoff,'limit':'-1','fl':'timestamp,original,statuscode,mimetype'})
    # CDX supports repeated filter parameters.
    query=query.replace('filter%21=', 'filter=')
    index=fetcher.fetch('https://web.archive.org/cdx/search/cdx?'+query)
    entries=json.loads(index.decoded_html)
    if len(entries)<2: return None
    stamp,original,status,mime=entries[-1]
    if not re.fullmatch(r'\d{14}',stamp) or status!='200' or 'html' not in mime: return None
    if clean_url(original)!=clean_url(url): return None
    archived_url=f'https://web.archive.org/web/{stamp}id_/{original}'
    capture=fetcher.fetch(archived_url)
    text=normalize_html(capture.decoded_html,NormalizationConfig(remove_selectors=('nav','header','footer'))).text
    if len(text.strip())<200: return None
    label=datetime.strptime(stamp,'%Y%m%d%H%M%S').strftime('%d.%m.%Y')+' · Webarchiv'
    return text, {'label':label,'url':archived_url.replace('id_/', '/')}

def run_scan(payload):
    started = time.monotonic()
    def event(step, message): return {'type':'progress','step':step,'message':message}
    example = payload.get('example')
    yield event(0, 'Gespeicherten Stand laden' if example else 'Webseite aufrufen')
    warnings=[]
    if example:
        if example not in ('decathlon','mueller'): raise ValueError('Unbekanntes Beispiel.')
        data=json.loads((ROOT/'data'/f'{example}.json').read_text())
        yield event(1, 'AGB-Quellen geladen')
        before_info, after_info = data['before'], data['after']
        name, scope = data['name'], data['scope']
        before_text, after_text = before_info['text'], after_info['text']
        source_url = data['url']
    else:
        source_url = clean_url(payload.get('url',''))
        fetcher=BoundedFetcher()
        page=fetcher.fetch(source_url)
        yield event(1,'AGB-Link suchen')
        target=discover(page)
        if not target: raise ValueError('Keine AGB-Seite gefunden. Bitte die direkte AGB-URL eingeben.')
        if target != page.final_url: page=fetcher.fetch(target)
        if 'html' not in dict((k.lower(),v) for k,v in page.headers).get('content-type','text/html').lower():
            raise ValueError('Bitte eine AGB-Seite im HTML-Format verwenden.')
        after_text=normalize_html(page.decoded_html,NormalizationConfig(remove_selectors=('nav','header','footer'))).text
        if len(after_text.strip())<200: raise ValueError('AGB-Extraktion zu kurz. Kein verlässlicher Vergleich möglich.')
        name=urlsplit(page.final_url).hostname
        scope='Live-Abruf · technischer Textvergleich'
        after_info={'label':datetime.now(timezone.utc).strftime('%d.%m.%Y · Live'),'url':page.final_url}
        previous=payload.get('previous')
        before_text=''
        before_info={'label':'Kein früherer Stand','url':page.final_url}
        if previous:
            if not isinstance(previous,dict) or previous.get('url')!=page.final_url or previous.get('version')!='scan-v1':
                raise ValueError('Der gespeicherte Stand gehört nicht zu dieser AGB-Seite.')
            parts=previous.get('paragraphs',[])
            if not isinstance(parts,list) or len(parts)>500 or any(not isinstance(p,str) for p in parts): raise ValueError('Ungültiger gespeicherter Stand.')
            if digest(parts)!=previous.get('hash'): raise ValueError('Prüfsumme des gespeicherten Stands stimmt nicht.')
            before_text='\n\n'.join(parts)
            before_info={'label':previous.get('label','Vorheriger Scan'),'url':page.final_url}
        if not previous:
            yield event(2,'Älteren Wayback-Stand suchen')
            try:
                archived=saved_baseline(page.final_url) or archived_baseline(page.final_url,BoundedFetcher())
                if archived: before_text,before_info=archived
                else: warnings.append('Kein passender älterer Wayback-Stand gefunden. Dieser Scan bildet den ersten Stand.')
            except (FetchFailure,ValueError,KeyError,TypeError,OSError):
                warnings.append('Wayback derzeit nicht verfügbar. Dieser Scan bildet den ersten Stand.')
        checks=(page.browser_metadata or {}).get('robots_checks',[])
        if any(x.get('status')=='ungeprueft' for x in checks): warnings.append('robots.txt konnte nicht vollständig geprüft werden.')
    yield event(2,'Absätze normalisieren')
    before,after=paragraphs(before_text),paragraphs(after_text)
    if not after or len(after)>500: raise ValueError('Dokument leer oder zu umfangreich (maximal 500 Absätze).')
    yield event(3,'SHA-256 bilden')
    old_hash,new_hash=digest(before),digest(after)
    yield event(4,'Absätze vergleichen')
    rows=compare(before,after) if before else []
    changed=sum(row['kind']!='equal' for row in rows)
    snapshot={'url':after_info['url'],'paragraphs':after,'hash':new_hash,'label':after_info['label'],'version':'scan-v1'}
    yield {'type':'result','name':name,'scope':scope,'before':{**{k:v for k,v in before_info.items() if k!='text'},'hash':old_hash if before else None},'after':{**{k:v for k,v in after_info.items() if k!='text'},'hash':new_hash},'rows':rows,'changed':changed,'total':len(after),'baselineCreated':not before,'snapshot':snapshot,'warnings':warnings,'seconds':round(time.monotonic()-started,2),'example':bool(example)}
