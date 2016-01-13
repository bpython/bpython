#!/bin/bash
set -e
set -x

pip install setuptools

if [[ $RUN == nosetests ]]; then
    # core dependencies
    pip install pygments
    pip install requests
    pip install 'curtsies >=0.1.17'
    pip install greenlet
    pip install 'six >=1.5'
    # filewatch specific dependencies
    pip install watchdog
    # jedi specific dependencies
    pip install jedi
    # translation specific dependencies
    pip install babel
    # Python 2.6 specific dependencies
    if [[ $TRAVIS_PYTHON_VERSION == 2.7 ]]; then
      # dependencies for crasher tests
      pip install Twisted urwid
    fi
    case $TRAVIS_PYTHON_VERSION in
      2*|pypy)
        # test specific dependencies
        pip install mock
        ;;
    esac
    # build and install
    python setup.py install
elif [[ $RUN == build_sphinx ]]; then
    # documentation specific dependencies
    pip install sphinx
fi
