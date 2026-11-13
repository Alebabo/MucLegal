"""Local static+API smoke server for the lite scanner; uvicorn is a dev dependency only."""
from pathlib import Path
from api.index import app
from fastapi import HTTPException
from fastapi.responses import FileResponse
ROOT=Path(__file__).resolve().parent
STATIC={'index.html':'text/html','style.css':'text/css','design.css':'text/css','app.js':'application/javascript',
        'evidence.js':'application/javascript','muclegal-logo.png':'image/png'}
FONTS={'.css':'text/css','.woff2':'font/woff2'}
@app.get('/')
def home(): return FileResponse(ROOT/'index.html',media_type='text/html')
@app.get('/fonts/{name}')
def font(name:str):
    path=ROOT/'fonts'/name
    if path.parent!=ROOT/'fonts' or path.suffix not in FONTS or not path.is_file(): raise HTTPException(404)
    return FileResponse(path,media_type=FONTS[path.suffix])
@app.get('/{name}')
def static(name:str):
    if name not in STATIC: raise HTTPException(404)
    return FileResponse(ROOT/name,media_type=STATIC[name])
