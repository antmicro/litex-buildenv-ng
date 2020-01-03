#!/bin/bash

source .travis/common.sh
set -e

# Close the after_success fold travis has created already.
travis_fold end after_success

start_section "success.tail" "${GREEN}Success output...${NC}"
echo "Log is $(wc -l build/build.log) lines long."
echo "Displaying last 1000 lines"
echo
tail -n 1000 build/build.log
end_section "success.tail"
