#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _maybe_reexec_with_venv_python() -> None:
    """Re-launch with backend/venv when it exists (avoids missing deps like celery)."""
    if os.environ.get('DJANGO_VENV_REEXEC') == '1':
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if os.name == 'nt':
        venv_python = os.path.join(base_dir, 'venv', 'Scripts', 'python.exe')
    else:
        venv_python = os.path.join(base_dir, 'venv', 'bin', 'python')

    if not os.path.isfile(venv_python):
        return

    current = os.path.normcase(os.path.abspath(sys.executable))
    target = os.path.normcase(os.path.abspath(venv_python))
    if current == target:
        return

    os.environ['DJANGO_VENV_REEXEC'] = '1'
    os.execv(venv_python, [venv_python, *sys.argv])


def main():
    """Run administrative tasks."""
    _maybe_reexec_with_venv_python()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
