#!/bin/bash

source .travis/common.sh

LITEX_SETUPS=`find third_party -name "setup.py" | grep "third_party/.*/setup.py"`
readarray -t LITEX_SETUPS_ARRAY <<< "$LITEX_SETUPS"

if [[ -z $CPU_VARIANT ]]; then
	source bootstrap.sh --cpu $CPU --platform $P --target $T --firmware $F
else
	source bootstrap.sh --cpu $CPU --cpu-variant $CPU_VARIANT --platform $P --target $T --firmware $F
fi

for setup in "${LITEX_SETUPS_ARRAY[@]}"; do
	cd `echo $setup | cut -d"/" -f1-2`
	python setup.py develop
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
