import gettext
import locale
import os.path
import sys

from bpython import package_dir

translator = None

if sys.version_info >= (3, 0):
    def _(message):
        return translator.gettext(message)
else:
    def _(message):
        return translator.ugettext(message)


def init(locale_dir=None, languages=None):
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        # This means that the user's environment is broken. Let's just continue
        # with the default C locale.
        sys.stderr.write("Error: Your locale settings are not supported by "
                         "the system. Using the fallback 'C' locale instead. "
                         "Please fix your locale settings.\n")

    global translator
    if locale_dir is None:
        locale_dir = os.path.join(package_dir, 'translations')

    translator = gettext.translation('bpython', locale_dir, languages,
                                     fallback=True)

