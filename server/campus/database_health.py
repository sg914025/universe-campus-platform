"""Read-only, bounded SQLite diagnostics. Author: UniVerse Team."""
from contextlib import closing
from pathlib import Path
import sqlite3
import time

from django.utils import timezone


def inspect_database(path, full=False, timeout=12):
    """Never return row contents, credentials, absolute paths or raw SQL errors."""
    path = Path(path).resolve()
    started = time.monotonic()
    report = {'checked_at': timezone.now().isoformat(), 'mode': 'full' if full else 'quick',
              'healthy': False, 'completed': False, 'integrity_ok': None,
              'foreign_key_errors': None, 'error': '', 'tables': []}
    try:
        with path.open('rb') as stream:
            if stream.read(16) != b'SQLite format 3\x00':
                raise ValueError('Invalid SQLite header')
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=3)) as db:
            db.execute('PRAGMA query_only=ON')
            db.set_progress_handler(lambda: int(time.monotonic()-started > timeout), 1000)
            # One read snapshot: counts and checks must describe the same database state.
            db.execute('BEGIN')
            pragma = 'integrity_check(10)' if full else 'quick_check(10)'
            report['integrity_ok'] = list(db.execute('PRAGMA '+pragma)) == [('ok',)]
            report['foreign_key_errors'] = sum(1 for _ in db.execute('PRAGMA foreign_key_check'))
            report['journal_mode'] = db.execute('PRAGMA journal_mode').fetchone()[0]
            report['page_size'] = db.execute('PRAGMA page_size').fetchone()[0]
            report['page_count'] = db.execute('PRAGMA page_count').fetchone()[0]
            report['free_pages'] = db.execute('PRAGMA freelist_count').fetchone()[0]
            report['index_count'] = db.execute("SELECT count(*) FROM sqlite_master WHERE type='index'").fetchone()[0]
            names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            report['table_count'] = len(names)
            # Full inspection and restore drills verify that all tables can be read.
            if full:
                for name in names:
                    count = db.execute('SELECT count(*) FROM "'+name.replace('"', '""')+'"').fetchone()[0]
                    report['tables'].append({'table': name, 'rows': count})
            db.rollback()
        report['size'] = path.stat().st_size
        wal = Path(str(path)+'-wal')
        report['wal_size'] = wal.stat().st_size if wal.exists() else 0
        report['healthy'] = report['integrity_ok'] and report['foreign_key_errors'] == 0
        report['completed'] = True
    except (OSError, ValueError, sqlite3.Error):
        report['error'] = 'check_incomplete'
    report['duration_ms'] = round((time.monotonic()-started)*1000)
    return report


def record_inspection(actor=None):
    from .models import DatabaseInspection
    from .security_service import database_path
    report = inspect_database(database_path(), full=True)
    return DatabaseInspection.objects.create(actor=actor, healthy=report['healthy'], report=report)
