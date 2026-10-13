import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scan import compare, paragraphs, digest, run_scan, clean_url
import pytest

def test_deterministic_examples():
    for name in ('decathlon','mueller'):
        a=list(run_scan({'example':name}))[-1]
        b=list(run_scan({'example':name}))[-1]
        assert a['rows']==b['rows'] and a['after']['hash']==b['after']['hash']
        assert a['changed']>0 and not a['baselineCreated']

def test_duplicate_paragraphs_are_preserved():
    rows=compare(['A','A','B'],['A','B'])
    assert len([r for r in rows if r['kind']=='delete'])==1
    assert ''.join(p['text'] for r in rows for p in r['right'])=='AB'

def test_insert_delete_and_word_diff():
    rows=compare(['Preis: 10 Euro.','Wegfall.'],['Preis: 20 Euro.'])
    assert rows[0]['kind']=='replace' and rows[1]['kind']=='delete'
    assert any(p['changed'] and p['text']=='10' for p in rows[0]['left'])
    assert any(p['changed'] and p['text']=='20' for p in rows[0]['right'])

def test_layout_wraps_do_not_change_legal_paragraph_hash():
    a=paragraphs('§1 Vertrag\n(1) Der Vertrag ist\nwirksam.\n(2) Ende.')
    b=paragraphs('§1 Vertrag\n(1) Der Vertrag ist wirksam.\n(2) Ende.')
    assert a==b and digest(a)==digest(b)

@pytest.mark.parametrize('url',['file:///etc/passwd','https://user:pw@example.com','https://example.com:22'])
def test_invalid_urls(url):
    with pytest.raises(ValueError): clean_url(url)

def test_muller_has_complete_wayback_baseline():
    result=list(run_scan({'example':'mueller'}))[-1]
    assert 'Vollständige AGB' in result['scope']
    assert 'web.archive.org' in result['before']['url']
    assert result['total']>30 and result['changed']>0

def test_live_baseline_then_compare(monkeypatch):
    from types import SimpleNamespace
    import scan
    text='<html><main><h1>AGB</h1><p>(1) '+('Vertrag gültig. '*30)+'</p><p>(2) Preis 10 Euro.</p></main></html>'
    fetched=SimpleNamespace(final_url='https://example.com/agb',decoded_html=text,headers=(('Content-Type','text/html'),),browser_metadata={})
    monkeypatch.setattr(scan.BoundedFetcher,'fetch',lambda self,url:fetched)
    monkeypatch.setattr(scan,'archived_baseline',lambda url,fetcher:None)
    first=list(run_scan({'url':fetched.final_url}))[-1]
    assert first['baselineCreated'] and not first['rows']
    second=list(run_scan({'url':fetched.final_url,'previous':first['snapshot']}))[-1]
    assert not second['baselineCreated'] and second['changed']==0
    fetched.decoded_html=text.replace('10 Euro','20 Euro')
    third=list(run_scan({'url':fetched.final_url,'previous':first['snapshot']}))[-1]
    assert third['changed']==1
    forged={**first['snapshot'],'hash':'fake'}
    with pytest.raises(ValueError): list(run_scan({'url':fetched.final_url,'previous':forged}))


def test_live_uses_wayback_when_no_previous_scan(monkeypatch):
    from types import SimpleNamespace
    import scan
    html='<html><main><h1>AGB</h1><p>(1) '+('Vertrag gültig. '*30)+'</p><p>(2) Preis 20 Euro.</p></main></html>'
    fetched=SimpleNamespace(final_url='https://example.com/agb',decoded_html=html,headers=(('Content-Type','text/html'),),browser_metadata={})
    monkeypatch.setattr(scan.BoundedFetcher,'fetch',lambda self,url:fetched)
    current=scan.normalize_html(html,scan.NormalizationConfig(remove_selectors=('nav','header','footer'))).text
    monkeypatch.setattr(scan,'archived_baseline',lambda url,f:(current.replace('20 Euro','10 Euro'),{'label':'01.01.2025 · Webarchiv','url':'https://web.archive.org/web/20250101000000/https://example.com/agb'}))
    result=list(run_scan({'url':fetched.final_url}))[-1]
    assert not result['baselineCreated'] and result['changed']==1
    assert 'web.archive.org' in result['before']['url']


def test_inserted_section_does_not_misalign_changed_clause():
    old=['4. Widerruf: Binnen 14 Tagen kann der Vertrag widerrufen werden.','5. Rücksendung: Die Rücksendung ist kostenlos.']
    new=['4. Vorbestellung: Neu und unabhängig geregelt.','5. Widerruf: Binnen 30 Tagen kann der Vertrag widerrufen werden.','6. Rücksendung: Die Rücksendung ist kostenlos.']
    rows=compare(old,new)
    assert rows[0]['kind']=='insert'
    assert rows[1]['kind']=='replace'
    assert 'Widerruf' in ''.join(p['text'] for p in rows[1]['left'])
    assert 'Widerruf' in ''.join(p['text'] for p in rows[1]['right'])
