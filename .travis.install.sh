#!/bin/bash
set -e
set -x

pip install setuptools

if [[ $RUN == nosetests ]]; then
    # core dependencies
    pip install pygments requests 'curtsies >=0.1.17,<0.2.0' greenlet
    # filewatch specific dependencies
    pip install watchdog
    # jedi specific dependencies
    pip install jedi
    # translation specific dependencies
    pip install babel
    # Python 2.6 specific dependencies
    if [[ $TRAVIS_PYTHON_VERSION == 2.6 ]]; then
      pip install unittest2
    fi
    # dependencies for crasher tests
    case $TRAVIS_PYTHON_VERSION in
      2*)
        pip install Twisted urwid
        ;;
    esac
    # build and install
    python setup.py install
elif [[ $RUN == build_sphinx ]]; then
    # documentation specific dependencies
    pip install sphinx
fi
