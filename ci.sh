#!/bin/sh
set -e
set -x
THIS_DIR=`cd $(dirname $0) ; pwd -P`

if [ "$(uname)" == "Darwin" ]; then
    HOST=darwin-x86
else
    HOST=linux-x86
fi

ENTRY_POINT=$THIS_DIR/ci.py
PYTHON_PATH=$(dirname $THIS_DIR)/prebuilts/python/$HOST/bin/python3
export PYTHONDONTWRITEBYTECODE=1
$PYTHON_PATH $ENTRY_POINT "$@"
