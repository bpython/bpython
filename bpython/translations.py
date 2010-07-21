import os.path
import gettext

try:
    translation = gettext.translation('bpython')
except IOError:
    # try to load .mo files created with 'python setup.py build_translation'
    # from the build/ directory
    try:
        translation = gettext.translation('bpython',
                            os.path.join('i18n', 'locale'))
    except IOError:
        translation = None

if translation is None:
    def _(s):
        return s
else:
    _ = translation.ugettext
