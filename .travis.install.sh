#!/bin/bash
set -e
set -x

pip install setuptools

if [[ $RUN == nosetests ]]; then
    # core dependencies
    pop install -r requirements.txt
    # filewatch specific dependencies
    pip install watchdog
    # jedi specific dependencies
    pip install jedi
    # translation specific dependencies
    pip install babel
    # Python 2.7 specific dependencies
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
    pip install 'sphinx >=1.1.3'
fi
