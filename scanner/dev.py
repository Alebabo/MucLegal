"""Local static+API smoke server; uvicorn is a development dependency only."""
from pathlib import Path
from api.index import app
from fastapi.responses import FileResponse
ROOT=Path(__file__).resolve().parent
@app.get('/')
def home(): return FileResponse(ROOT/'index.html')
@app.get('/app.js')
def js(): return FileResponse(ROOT/'app.js',media_type='application/javascript')
@app.get('/style.css')
def css(): return FileResponse(ROOT/'style.css',media_type='text/css')
