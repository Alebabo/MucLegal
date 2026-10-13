"""Copy only the existing HTTP and normalization engines into the small deployment."""
from pathlib import Path
import shutil
root = Path(__file__).resolve().parent
shared = root.parent / 'muclegal'
(root / 'engine').mkdir(exist_ok=True)
(root / 'engine' / '__init__.py').touch()
for source, target in [('normalize/core.py', 'core.py'), ('fetch/http.py', 'http.py')]:
    if (shared / source).exists():
        text = (shared / source).read_text()
        if target == 'http.py':
            text = text.replace('response.read()', 'response.read(2_000_001)')
        (root / 'engine' / target).write_text(text)
    elif not (root / 'engine' / target).exists():
        raise RuntimeError('Missing shared engine: ' + source)

(root / 'public').mkdir(exist_ok=True)
for name in ('index.html', 'style.css', 'design.css', 'app.js', 'muclegal-logo.png'):
    shutil.copyfile(root / name, root / 'public' / name)

shutil.copytree(root / 'fonts', root / 'public' / 'fonts', dirs_exist_ok=True)
