# PYTHON_ARGCOMPLETE_OK
"""The ``arioso`` command line (also ``python -m arioso``).

Examples::

    arioso generate "warm lo-fi piano" --platform musicgen --duration 10 -o out.wav
    arioso platforms
"""

from __future__ import annotations

import functools

import cw

from arioso.cli import commands

#: Failures a user can fix (an unknown platform, a bad value, a missing optional
#: dependency): one line on stderr instead of a traceback.
EXPECTED_ERRORS = (KeyError, ValueError, ImportError)


def _expected_errors_as_messages(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except EXPECTED_ERRORS as error:
            message = error.args[0] if isinstance(error, KeyError) else error
            raise cw.CommandError(str(message)) from error

    return wrapper


def main(argv=None) -> int:
    """Run the ``arioso`` command line on *argv* (default ``sys.argv[1:]``).

    Returns:
        The process exit code.
    """
    return cw.dispatch(
        {name: _expected_errors_as_messages(f) for name, f in commands.items()},
        argv,
        convention=cw.MODERN,  # resolves annotations, so --seed arrives as an int
    )


if __name__ == "__main__":
    raise SystemExit(main())
