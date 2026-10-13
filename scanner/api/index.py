import json
import logging
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
from scan import run_scan
from i18n import translate, FAILURES
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
@app.post('/api/scan')
@app.post('/api/index')
async def scan(request: Request):
    body=await request.body()
    if len(body)>250_000: return JSONResponse({'error':'Anfrage zu groß.'},status_code=413)
    try:
        payload=json.loads(body)
        if not isinstance(payload,dict): raise ValueError()
    except (ValueError,TypeError): return JSONResponse({'error':'Ungültige Anfrage.'},status_code=400)
    language=payload.get("language", "de")
    def stream():
        try:
            for event in run_scan(payload):
                if 'message' in event: event['message']=translate(event['message'],language)
                if 'warnings' in event: event['warnings']=[translate(w,language) for w in event['warnings']]
                yield json.dumps(event,ensure_ascii=False)+'\n'
        except Exception as exc:
            logging.warning('scan_failed: %s',type(exc).__name__)
            message=str(exc) if isinstance(exc,ValueError) or hasattr(exc,'code') else 'Scan fehlgeschlagen. Bitte später erneut versuchen.'
            if language=='en': message=FAILURES.get(getattr(exc,'code',''), 'The page could not be retrieved safely. Please check the URL or try again.') if hasattr(exc,'code') else translate(message,language)
            yield json.dumps({'type':'error','message':message},ensure_ascii=False)+'\n'
    return StreamingResponse(stream(),media_type='application/x-ndjson',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
