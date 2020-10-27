#!/bin/bash
set -e
set -x

pip install setuptools

if [[ $RUN == nosetests ]]; then
    # core dependencies
    pip install -r requirements.txt
    # urwid specific dependencies
    pip install urwid twisted
    # filewatch specific dependencies
    pip install watchdog
    # jedi specific dependencies
    pip install 'jedi >= 0.16'
    # translation specific dependencies
    pip install babel
    # build and install
    python setup.py install
elif [[ $RUN == build_sphinx ]]; then
    # documentation specific dependencies
    pip install 'sphinx >=1.5'
fi
