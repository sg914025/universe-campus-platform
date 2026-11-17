"""Run Django with an optional project-local environment file; never execute it as code."""
import os
import runpy
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'server'
env_file = root / '.env'
if env_file.is_file():
    for line in env_file.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not key.strip().replace('_', '').isalnum():
            raise ValueError('Invalid .env assignment')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
os.chdir(root)
import sys
sys.path.insert(0, str(root))
runpy.run_path(str(root / 'manage.py'), run_name='__main__')
