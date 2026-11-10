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


def _is_expected(error: Exception) -> bool:
    """Whether *error* is one a user can fix: a bad value (arioso raises ValueError
    for those) or a missing optional dependency. Anything else is a bug and keeps
    its traceback."""
    if isinstance(error, ModuleNotFoundError):
        return not (error.name or "").startswith("arioso")
    return isinstance(error, ValueError)


def _expected_errors_as_messages(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as error:
            if _is_expected(error):
                raise cw.CommandError(str(error)) from error
            raise

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
