#!/usr/bin/env python
import os
import sys
from pathlib import Path


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ModuleNotFoundError as error:
        if error.name != 'django':
            raise
        project_python = Path(__file__).resolve().parent / '.venv' / (
            'Scripts/python.exe' if os.name == 'nt' else 'bin/python'
        )
        if project_python.is_file() and project_python.resolve() != Path(sys.executable).resolve():
            print('Django is not installed in the selected Python. Using the project .venv.', flush=True)
            os.execv(str(project_python), [str(project_python), str(Path(__file__).resolve()), *sys.argv[1:]])
        raise SystemExit(
            'Django is missing. Install project dependencies with:\n'
            '  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt\n'
            'Then start the project using start.cmd.'
        ) from error
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
