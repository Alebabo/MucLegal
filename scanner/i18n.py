"""Translate interface metadata only; source documents always remain verbatim."""
EN={
'Gespeicherten Stand laden':'Loading saved versions', 'Webseite aufrufen':'Opening website',
'AGB-Quellen geladen':'Terms sources loaded','AGB-Link suchen':'Finding terms page',
'Älteren Wayback-Stand suchen':'Finding an older Wayback version','Absätze normalisieren':'Normalizing paragraphs',
'SHA-256 bilden':'Computing SHA-256','Absätze vergleichen':'Comparing paragraphs',
'Bitte eine öffentliche HTTP(S)-Webseite ohne Zugangsdaten eingeben.':'Enter a public HTTP(S) website without credentials.',
'Die URL ist zu lang.':'The URL is too long.', 'Unbekanntes Beispiel.':'Unknown example.',
'Keine AGB-Seite gefunden. Bitte die direkte AGB-URL eingeben.':'No terms page found. Please enter the direct terms URL.',
'Bitte eine AGB-Seite im HTML-Format verwenden.':'Please use an HTML terms page.',
'AGB-Extraktion zu kurz. Kein verlässlicher Vergleich möglich.':'The extracted terms are too short for a reliable comparison.',
'Der gespeicherte Stand gehört nicht zu dieser AGB-Seite.':'The saved version belongs to a different terms page.',
'Ungültiger gespeicherter Stand.':'Invalid saved version.',
'Prüfsumme des gespeicherten Stands stimmt nicht.':'The saved version checksum does not match.',
'Dokument leer oder zu umfangreich (maximal 500 Absätze).':'Document empty or too large (maximum 500 paragraphs).',
'Seite zu groß (maximal 2 MB).':'Page too large (maximum 2 MB).','Zu viele Weiterleitungen.':'Too many redirects.',
'Kein passender älterer Wayback-Stand gefunden. Dieser Scan bildet den ersten Stand.':'No older matching Wayback version found. This scan creates the first version.',
'Wayback derzeit nicht verfügbar. Dieser Scan bildet den ersten Stand.':'Wayback is currently unavailable. This scan creates the first version.',
'robots.txt konnte nicht vollständig geprüft werden.':'robots.txt could not be fully checked.',
'Scan fehlgeschlagen. Bitte später erneut versuchen.':'Scan failed. Please try again later.',
'Anfrage zu groß.':'Request too large.','Ungültige Anfrage.':'Invalid request.'
}
FAILURES={'network_error':'The website could not be reached. Please try again later.',
'dns_error':'The website hostname could not be resolved.',
'robots_disallowed':'robots.txt does not allow this page to be retrieved.',
'protected_or_login_page':'This page requires authentication or blocks automated retrieval.',
'http_error':'The website returned an HTTP error.',
'invalid_url':'Please enter a valid public HTTP(S) URL.'}
def translate(text,language): return EN.get(text,text) if language=='en' else text
