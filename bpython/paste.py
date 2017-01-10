# encoding: utf-8

# The MIT License
#
# Copyright (c) 2014-2015 Sebastian Ramacher
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from __future__ import absolute_import

from locale import getpreferredencoding
from six.moves.urllib_parse import quote as urlquote, urljoin, urlparse
from string import Template
import errno
import requests
import subprocess
import unicodedata

from .translations import _


class PasteFailed(Exception):
    pass


class PastePinnwand(object):
    def __init__(self, url, expiry, show_url, removal_url):
        self.url = url
        self.expiry = expiry
        self.show_url = show_url
        self.removal_url = removal_url

    def paste(self, s):
        """Upload to pastebin via json interface."""

        url = urljoin(self.url, '/json/new')
        payload = {
            'code': s,
            'lexer': 'pycon',
            'expiry': self.expiry
        }

        try:
            response = requests.post(url, data=payload, verify=True)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise PasteFailed(exc.message)

        data = response.json()

        paste_url_template = Template(self.show_url)
        paste_id = urlquote(data['paste_id'])
        paste_url = paste_url_template.safe_substitute(paste_id=paste_id)

        removal_url_template = Template(self.removal_url)
        removal_id = urlquote(data['removal_id'])
        removal_url = removal_url_template.safe_substitute(
            removal_id=removal_id)

        return (paste_url, removal_url)


class PasteHelper(object):
    def __init__(self, executable):
        self.executable = executable

    def paste(self, s):
        """Call out to helper program for pastebin upload."""

        try:
            helper = subprocess.Popen('',
                                      executable=self.executable,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)
            helper.stdin.write(s.encode(getpreferredencoding()))
            output = helper.communicate()[0].decode(getpreferredencoding())
            paste_url = output.split()[0]
        except OSError as e:
            if e.errno == errno.ENOENT:
                raise PasteFailed(_('Helper program not found.'))
            else:
                raise PasteFailed(_('Helper program could not be run.'))

        if helper.returncode != 0:
            raise PasteFailed(_('Helper program returned non-zero exit '
                                'status %d.' % (helper.returncode, )))

        if not paste_url:
            raise PasteFailed(_('No output from helper program.'))
        else:
            parsed_url = urlparse(paste_url)
            if (not parsed_url.scheme or
                any(unicodedata.category(c) == 'Cc'
                    for c in paste_url)):
                raise PasteFailed(_('Failed to recognize the helper '
                                    'program\'s output as an URL.'))

        return paste_url, None
