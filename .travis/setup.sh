#!/bin/bash

source .travis/common.sh

python3 scripts/setup_litex.py

# Add non-standard configs to default.env configuration file if needed
# Additional configs should be ';' separated
export IFS=";"
read -ra ADDITIONAL_CONFIGS <<< "$A"
export IFS=""

echo "# Additional configs" >> default.env
for cfg in "${ADDITIONAL_CONFIGS[@]}"; do
	echo $cfg >> default.env
done
