import gettext
import os.path
from sys import version_info

from bpython import package_dir

translator = None

if version_info >= (3, 0):
    def _(message):
        return translator.gettext(message)
else:
    def _(message):
        return translator.ugettext(message)


def init(locale_dir=None, languages=None):
    global translator
    if locale_dir is None:
        locale_dir = os.path.join(package_dir, 'translations')

    translator = gettext.translation('bpython', locale_dir, languages,
                                     fallback=True)

