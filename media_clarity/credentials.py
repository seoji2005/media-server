"""Optional hidden, session-only Gemini key input before starting the app."""
from contextlib import contextmanager
import getpass
import os
import warnings

from . import gemini
from .storage import MediaError


@contextmanager
def prompt_gemini_key(enabled):
    if not enabled or gemini.configured():
        yield
        return
    previous = os.environ.get('GEMINI_API_KEY')
    try:
        # getpass otherwise falls back to echoed stdin when no terminal exists.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            key = getpass.getpass('Gemini API key (hidden; Enter for viewing only): ')
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt, OSError):
        raise MediaError('gemini_key_input_unavailable', 503) from None
    if key:
        try:
            gemini.validate_key(key)
        except MediaError:
            raise MediaError('gemini_key_invalid', 422) from None
    try:
        os.environ.pop('GEMINI_API_KEY', None)
        if key:
            os.environ['GEMINI_API_KEY'] = key
        yield
    finally:
        if previous is None:
            os.environ.pop('GEMINI_API_KEY', None)
        else:
            os.environ['GEMINI_API_KEY'] = previous
