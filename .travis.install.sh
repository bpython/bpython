#!/bin/bash
set -e
set -x

pip install setuptools

if [[ $RUN == nosetests ]] then
    # core dependencies
    pip install pygments requests 'curtsies >=0.1.16,<0.2.0' greenlet
    # filewatch specific dependencies
    pip install watchdog
    # translation specific dependencies
    pip install babel
    # Python 2.6 specific dependencies
    if [[ $TRAVIS_PYTHON_VERSION == 2.6 ]] then
      pip install unittest
    fi
    # build and install
    python setup.py install
elif [[ $RUN == build_sphinx ]] then
    # documentation specific dependencies
    pip install sphinx
fi
