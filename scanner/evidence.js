// Evidence view: screenshots and normalized texts from the local BeweisLab.
// Only active when the page is served by the MucLegal app (data-evidence="on");
// the Vercel scanner has no capture backend and keeps the button hidden.
(()=>{
const enabled=document.body.dataset.evidence==='on';
const text={
de:{button:'Evidence ↗',close:'Schließen ✕',recapture:'Neu erfassen ↗',title:'Evidence',scope:'BeweisLab · Screenshots und normalisierte Texte',
oldVersion:'Alte Version',newVersion:'Neue Version',screenshot:'Screenshot',normalized:'Normalisierter Text',
download:'Beweispaket ↓',openImage:'Original öffnen ↗',noImage:'Kein Screenshot für diesen Stand. Angezeigt wird der normalisierte Text aus dem Scan.',
noImageRole:'Für diese Seite liegt kein Screenshot vor.',
scanText:'Normalisierter Text aus dem Scan (ohne Beweisbild).',noPrevious:'Kein früherer Stand vorhanden.',
preparing:'Gespeicherte Beweisstände werden geladen …',capturing:'Live-Erfassung im BeweisLab läuft …',
captured:'Beweise erfasst.',loaded:'Beweisstände geladen.',cached:'Gespeicherte Erfassung dieses Textstands.',
liveNote:'Live-Erfassung vom {date} · God Mode. Kann vom gespeicherten Vergleichsstand abweichen.',
demoNote:'Hinterlegter Demo-Beweisstand.',
standard:'God Mode: robots.txt wird ignoriert (Nutzeranweisung 13.11.2026). Zulässigkeit des Abrufs selbst prüfen. Logins, Paywalls und CAPTCHAs werden nicht umgangen.',
notConfigured:'Live-Erfassung ist in dieser Instanz nicht konfiguriert.',busy:'Es läuft bereits eine Erfassung. Bitte kurz warten.',
failed:'Erfassung fehlgeschlagen.',noCase:'Die Erfassung lieferte kein Beweispaket.',
tile:(i,n)=>'Abschnitt '+i+' / '+n,loading:'Text wird geladen …',legacy:'Erweitertes BeweisLab ↗'},
en:{button:'Evidence ↗',close:'Close ✕',recapture:'Capture again ↗',title:'Evidence',scope:'BeweisLab · screenshots and normalized texts',
oldVersion:'Old version',newVersion:'New version',screenshot:'Screenshot',normalized:'Normalized text',
download:'Evidence package ↓',openImage:'Open original ↗',noImage:'No screenshot for this version. Showing the normalized text from the scan.',
noImageRole:'No screenshot is available for this page.',
scanText:'Normalized text from the scan (no evidence image).',noPrevious:'No previous version available.',
preparing:'Loading saved evidence …',capturing:'Live capture in BeweisLab running …',
captured:'Evidence captured.',loaded:'Evidence loaded.',cached:'Saved capture of this text version.',
liveNote:'Live capture from {date} · God Mode. May differ from the saved comparison version.',
demoNote:'Stored demo evidence.',
standard:'God Mode: robots.txt is ignored (user instruction 2026-11-13). Check that retrieval is permitted. Logins, paywalls and CAPTCHAs are not bypassed.',
notConfigured:'Live capture is not configured in this instance.',busy:'Another capture is running. Please wait a moment.',
failed:'Capture failed.',noCase:'The capture produced no evidence package.',
tile:(i,n)=>'Section '+i+' / '+n,loading:'Loading text …',legacy:'Advanced BeweisLab ↗'}
};
const stepLabels={de:{queued:'Vorbereitung',fetch:'Seite abrufen',browser:'Browser-Erfassung',normalize:'Inhalt aufbereiten',legal_pages:'Rechtstexte suchen',screenshot:'Ansicht festhalten',compare:'Stand einordnen',warc:'Archiv erstellen',manifest:'Prüfwerte bilden',timestamp:'Zeitpunkt belegen'},
en:{queued:'Preparing',fetch:'Fetch page',browser:'Browser capture',normalize:'Prepare content',legal_pages:'Find legal texts',screenshot:'Capture view',compare:'Classify version',warc:'Create archive',manifest:'Compute checksums',timestamp:'Prove time'}};
const roleOrder=['agb','main','privacy','requested'];
const terminal=new Set(['completed','completed_with_warnings','failed','protected','baseline_created','unchanged']);
// `language` is app.js's global binding (classic scripts share one global scope).
const lang=()=>typeof language==='string'&&language==='en'?'en':'de';
const L=(key,...args)=>{const v=text[lang()][key];return typeof v==='function'?v(...args):v};
const el=id=>document.getElementById(id);
const section=el('evidence'),button=el('evidence-button');
let current=null,state=null,running=false,generation=0;
const evidenceKey=hash=>'muclegal:evidence-v1:'+hash;
function remember(hash,caseId){if(!hash||!caseId)return;try{localStorage.setItem(evidenceKey(hash),caseId)}catch{}}
function recall(hash){if(!hash)return null;try{return localStorage.getItem(evidenceKey(hash))}catch{return null}}
async function api(url,options){const r=await fetch(url,options);if(!r.ok){let m='HTTP '+r.status;try{const body=await r.json();m=body.detail||body.error||m}catch{}const e=Error(m);e.status=r.status;throw e}return r.json()}
const exampleId=result=>result.example?(result.name==='Müller'?'mueller':'decathlon'):null;
function scanParagraphs(side){if(!current)return [];if(side==='new')return current.snapshot?.paragraphs||[];return current.rows.filter(r=>r.oldNumber!=null).map(r=>r.left.map(p=>p.text).join(''))}

function setStatus(message,kind=''){const s=el('evidence-status');s.textContent=message||'';s.dataset.kind=kind}
function showError(message){const e=el('evidence-error');e.textContent=message;e.hidden=!message}
function setButtons(){button.disabled=running;button.textContent=L('button');el('evidence-close').textContent=L('close');const re=el('evidence-recapture');re.textContent=L('recapture');re.hidden=!state||running||!current||Boolean(exampleId(current)==='decathlon');re.disabled=running}
function renderLog(run){const log=el('evidence-log');log.hidden=false;log.replaceChildren();(run.audit_log||[]).forEach((item,index,all)=>{const li=document.createElement('li');const active=index===all.length-1&&!terminal.has(run.status);li.className='evidence-log-item '+(item.state==='failed'?'failed':active?'active':'done');const b=document.createElement('b');b.textContent=stepLabels[lang()][item.step]||item.step;const p=document.createElement('span');p.textContent=item.message||'';li.append(b,p);log.append(li)});log.scrollTop=log.scrollHeight}

async function streamCapture(url){
  const response=await fetch('/api/v1/evidence-runs/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,verification_mode:true,god_mode_authorized:true})});
  if(!response.ok){let m='HTTP '+response.status;try{m=(await response.json()).detail||m}catch{}const e=Error(m);e.status=response.status;throw e}
  const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',done=null;
  const consume=line=>{if(!line.trim())return;const msg=JSON.parse(line);if(msg.type==='error')throw Error(msg.detail||L('failed'));if(msg.run){renderLog(msg.run);if(msg.type==='complete')done=msg.run}};
  while(true){const {value,done:end}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!end});let i;while((i=buffer.indexOf('\n'))>=0){consume(buffer.slice(0,i));buffer=buffer.slice(i+1)}if(end){consume(buffer);break}}
  if(!done)throw Error(L('failed'));
  if(done.case_detail)return done.case_detail;
  if(!done.result_available)throw Error(done.message||L('noCase'));
  const index=await api('/api/cases'),list=[...(index.god_mode_cases||[]),...(index.cases||[])];
  const item=list.find(c=>c.requested_url===url)||list.find(c=>c.url===url);
  if(!item)throw Error(L('noCase'));
  return api('/api/cases/'+encodeURIComponent(item.case_id));
}
async function loadCase(caseId){try{return await api('/api/v1/cases/'+encodeURIComponent(caseId))}catch{return null}}

async function open(force=false){
  if(!current||running)return;
  const mine=++generation;running=true;section.hidden=false;button.setAttribute('aria-expanded','true');showError('');setButtons();
  el('evidence-log').hidden=true;el('evidence-columns').hidden=true;
  const result=current,example=exampleId(result);
  state={old:{detail:null,note:''},new:{detail:null,note:''}};
  try{
    if(example==='decathlon'){
      setStatus(L('preparing'));const prepared=await api('/api/v1/demo/decathlon',{method:'POST'});
      state.old={detail:await loadCase(prepared.baseline_evidence_case_id),note:L('demoNote')};
      state.new={detail:await loadCase(prepared.current_evidence_case_id),note:L('demoNote')};
      setStatus(L('loaded'),'ok');
    }else{
      if(example==='mueller'){setStatus(L('preparing'));const prepared=await api('/api/v1/demo/mueller',{method:'POST'});state.old={detail:await loadCase(prepared.baseline_evidence_case_id),note:L('demoNote')}}
      else{const oldId=recall(result.before.hash);if(oldId)state.old={detail:await loadCase(oldId),note:L('cached')}}
      const cachedNew=!force&&recall(result.after.hash);
      const cachedDetail=cachedNew?await loadCase(cachedNew):null;
      if(cachedDetail&&mine===generation){state.new={detail:cachedDetail,note:L('cached')};setStatus(L('loaded'),'ok')}
      else{
        setStatus(L('capturing')+' '+L('standard'));render();
        const detail=await streamCapture(result.after.url);
        if(mine!==generation)return;
        // Only reuse for later scans when the captured text belongs to this scan's hash.
        if(!example)remember(result.after.hash,detail.case_id);
        const date=new Date().toLocaleDateString(lang()==='en'?'en-GB':'de-DE');
        state.new={detail,note:L('liveNote').replace('{date}',date)};
        setStatus(L('captured'),'ok');
      }
    }
  }catch(error){
    if(mine!==generation)return;
    showError(error.status===404?L('notConfigured'):error.status===409?L('busy'):error.message||L('failed'));setStatus('');
  }finally{if(mine===generation){running=false;setButtons();render()}}
}

function galleryRoles(detail){const g=detail?.capture_galleries||{};return Object.keys(g).sort((a,b)=>{const ai=roleOrder.indexOf(a),bi=roleOrder.indexOf(b);return (ai<0?99:ai)-(bi<0?99:bi)})}
function images(gallery){if(!gallery)return [];if(gallery.tile_urls?.length)return gallery.tile_urls;if(gallery.original_urls?.length)return gallery.original_urls;return gallery.preview_url?[gallery.preview_url]:[]}

function column(side){
  const info=state[side],detail=info.detail,col=document.createElement('article');col.className='evidence-column';
  const head=document.createElement('div');head.className='evidence-head';const type=document.createElement('span');type.className='version-type';type.innerHTML='<i class="'+(side==='old'?'old-dot':'new-dot')+'"></i>';type.append(document.createTextNode(L(side==='old'?'oldVersion':'newVersion')));
  const src=document.createElement('a');const info2=current[side==='old'?'before':'after'];src.href=detail?.captured_url||detail?.url||info2.url;src.target='_blank';src.rel='noopener noreferrer';src.textContent=(detail?.captured_url||detail?.url||info2.url)+' ↗';
  head.append(type,src);
  if(info.note){const n=document.createElement('p');n.className='evidence-note';n.textContent=info.note;head.append(n)}
  col.append(head);
  const roles=galleryRoles(detail);
  if(!detail||!roles.length){
    const paragraphs=scanParagraphs(side);
    const note=document.createElement('p');note.className='evidence-note';note.textContent=paragraphs.length?L('noImage'):L('noPrevious');col.append(note);
    if(paragraphs.length){const pre=document.createElement('pre');pre.className='evidence-text';pre.textContent=paragraphs.join('\n\n');col.append(pre)}
    return col;
  }
  const controls=document.createElement('div');controls.className='evidence-controls';
  const roleSelect=document.createElement('select');roleSelect.setAttribute('aria-label','Seite / page');
  roles.forEach(role=>roleSelect.add(new Option(detail.capture_galleries[role].title||role,role)));
  roleSelect.hidden=roles.length<2;
  const tabs=document.createElement('div');tabs.className='evidence-tabs';tabs.setAttribute('role','tablist');
  const views={image:L('screenshot'),text:L('normalized')};const tabButtons={};
  Object.entries(views).forEach(([key,label])=>{const b=document.createElement('button');b.type='button';b.setAttribute('role','tab');b.textContent=label;b.dataset.view=key;tabButtons[key]=b;tabs.append(b)});
  controls.append(tabs,roleSelect);
  if(detail.download_url||detail.case_id){const dl=document.createElement('a');dl.className='evidence-download';dl.href=detail.download_url||('/api/v1/cases/'+encodeURIComponent(detail.case_id)+'/download');dl.textContent=L('download');controls.append(dl)}
  col.append(controls);
  const body=document.createElement('div');body.className='evidence-body';col.append(body);
  let view='image';
  async function show(){
    Object.entries(tabButtons).forEach(([key,b])=>b.setAttribute('aria-selected',String(key===view)));
    const gallery=detail.capture_galleries[roleSelect.value];body.replaceChildren();
    if(view==='image'){
      const list=images(gallery);
      if(!list.length){const p=document.createElement('p');p.className='evidence-note';p.textContent=L('noImageRole');body.append(p);return}
      list.forEach((url,index)=>{const figure=document.createElement('figure');const img=document.createElement('img');img.src=url;img.loading='lazy';img.alt=(gallery.title||'')+' · '+L('tile',index+1,list.length);figure.append(img);if(list.length>1){const cap=document.createElement('figcaption');cap.textContent=L('tile',index+1,list.length);figure.append(cap)}body.append(figure)});
      const openLink=document.createElement('a');openLink.className='evidence-open';openLink.href=list[0];openLink.target='_blank';openLink.rel='noopener';openLink.textContent=L('openImage');body.append(openLink);
      return;
    }
    const pre=document.createElement('pre');pre.className='evidence-text';
    if(!gallery.normalized_text_url){pre.textContent=scanParagraphs(side).join('\n\n');const n=document.createElement('p');n.className='evidence-note';n.textContent=L('scanText');body.append(n,pre);return}
    pre.textContent=L('loading');body.append(pre);
    try{const r=await fetch(gallery.normalized_text_url);if(!r.ok)throw Error('HTTP '+r.status);pre.textContent=await r.text()}catch(error){pre.textContent=error.message}
  }
  Object.values(tabButtons).forEach(b=>b.onclick=()=>{view=b.dataset.view;show()});
  roleSelect.onchange=show;show();
  return col;
}

function render(){
  el('evidence-scope').textContent=L('scope');el('evidence-title').textContent=L('title');setButtons();
  const cols=el('evidence-columns');
  if(!state||running&&!state.new.detail){cols.hidden=true;return}
  cols.replaceChildren(column('old'),column('new'));cols.hidden=false;
}

function reset(){generation++;running=false;current=null;state=null;section.hidden=true;button.hidden=true;button.setAttribute('aria-expanded','false');el('evidence-log').replaceChildren();showError('');setStatus('')}

window.muclegalEvidence={
  result(result){if(!enabled)return;if(result!==current){reset();current=result}button.hidden=false;setButtons()},
  reset(){if(enabled)reset()},
  language(){if(!enabled)return;const legacy=document.querySelector('.legacy-link');if(legacy)legacy.textContent=L('legacy');if(current)render()}
};
if(!enabled)return;
button.onclick=()=>{if(!state)open();else{section.hidden=false;button.setAttribute('aria-expanded','true')}section.scrollIntoView({behavior:'smooth',block:'start'})};
el('evidence-close').onclick=()=>{section.hidden=true;button.setAttribute('aria-expanded','false')};
el('evidence-recapture').onclick=()=>open(true);
// Keep the full legacy BeweisLab (case linking, Grey Mode, technical files) reachable.
const foot=document.querySelector('footer');if(foot){const a=document.createElement('a');a.href='/beweis-labor/klassisch';a.className='legacy-link';a.textContent=L('legacy');foot.append(a)}
})();
