#!/bin/sh
set -e
set -x
THIS_DIR=`cd $(dirname $0) ; pwd -P`
TOP=$(cd $THIS_DIR/..; pwd -P)

if [ "$(uname)" = "Darwin" ]; then
    HOST=darwin-x86
elif [ "$(uname -m)" = "aarch64" ]; then
    HOST=linux-arm64
else
    HOST=linux-x86
fi

export PATH=$TOP/prebuilts/build-tools/path/$HOST:$TOP/prebuilts/build-tools/$HOST/bin:$PATH

ENTRY_POINT=$THIS_DIR/ci.py
PYTHON_PATH=$(dirname $THIS_DIR)/prebuilts/python/$HOST/bin/python3
export PYTHONDONTWRITEBYTECODE=1
$PYTHON_PATH $ENTRY_POINT "$@"
