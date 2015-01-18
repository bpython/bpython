#!/bin/bash
set -e
set -x

if [[ $RUN == build_sphinx ]] then
    python setup.py build_sphinx
    python setup.py build_sphinx_man
elif [[ $RUN == nosetests ]] then
  cd build/lib/
  nosetests bpython/test
fi
