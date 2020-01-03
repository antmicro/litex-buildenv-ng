#!/bin/bash

source .travis/common.sh

LITEX_SETUPS=`find third_party -name "setup.py" | grep "third_party/.*/setup.py"`
readarray -t LITEX_SETUPS_ARRAY <<< "$LITEX_SETUPS"

for setup in "${LITEX_SETUPS_ARRAY[@]}"; do
	cd `echo $setup | cut -d"/" -f1-2`
	python3 setup.py develop
	cd -
done

# Add non-standard configs to default.env configuration file if needed
# Additional configs should be ';' separated
export IFS=";"
read -ra ADDITIONAL_CONFIGS <<< "$A"
export IFS=""

echo "# Additional configs" >> default.env
for cfg in "${ADDITIONAL_CONFIGS[@]}"; do
	echo $cfg >> default.env
done
