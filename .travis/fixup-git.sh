#!/bin/bash

source .travis/common.sh
set -e

# Git repo fixup
start_section "environment.git" "Setting up ${YELLOW}git checkout${NC}"
set -x
git fetch --unshallow || true
git fetch --tags
git submodule update --recursive --init
git submodule foreach git submodule update --recursive --init
$SPACER
git checkout $TRAVIS_BRANCH
git branch -v
git remote -v
#git branch -D $TRAVIS_BRANCH
#CURRENT_GITREV="$(git rev-parse HEAD)"
#git checkout -b $TRAVIS_BRANCH $CURRENT_GITREV
git tag -l
git status -v
git describe --long
set +x
end_section "environment.git"
