#!/bin/sh

if [ $# -eq 0 ]
  then
    echo "No arguments supplied"
    echo "Usage: build_all.sh [tag]"
    
    exit -1;
fi
cd core
docker build . --tag williangalvani/core:$1
cd -
cd supervisor
docker build . --tag williangalvani/supervisor:$1
cd -
cd bootstrap
docker build . --tag williangalvani/bootstrap:$1
