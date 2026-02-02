#!/bin/bash
set -e

top=$(cd $(dirname $0)/.. && pwd)
ndk_src=$top/ndk

docker build -t ndk-ci $ndk_src/infra/ci_docker
docker run -t -v$top:$top -w $top --entrypoint $ndk_src/ci.sh \
  ndk-ci "$@"
exit $?
