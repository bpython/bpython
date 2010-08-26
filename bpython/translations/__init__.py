import gettext
from sys import version_info


translator = None

if version_info >= (3, 0):
    def _(message):
        return translator.gettext(message)
else:
    def _(message):
        return translator.ugettext(message)


def init(locale_dir=None, languages=None):
    global translator
    translator = gettext.translation('bpython', locale_dir, languages,
                                     fallback=True)

init()
