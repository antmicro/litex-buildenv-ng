#!/bin/bash

source $TRAVIS_BUILD_DIR/.travis/common.sh

# Close the after_failure fold travis has created already.
travis_fold end after_failure

$SPACER

start_section "failure.tail" "${RED}Failure output...${NC}"
echo "Log is $(wc -l build/build.log) lines long."
echo "Displaying last 1000 lines"
echo
tail -n 1000 build/build.log
end_section "failure.tail"

$SPACER

start_section "failure.log.full" "${RED}Failure output.log...${NC}"
cat build/build.log
end_section "failure.log.full"
