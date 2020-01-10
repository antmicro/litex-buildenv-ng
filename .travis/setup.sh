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

if [ $TRAVIS_OS_NAME == 'osx' ]; then
	# Download non-standard elf.h for macOS
	wget https://gist.githubusercontent.com/mlafeldt/3885346/raw/2ee259afd8407d635a9149fcc371fccf08b0c05b/elf.h
	cp elf.h /usr/local/include

	# Replace xargs with gxargs
	ln -s `which gxargs` /usr/local/bin/xargs

	# Replace sed with gsed
	ln -s `which gsed` /usr/local/bin/sed

	# Replace stat with gstat
	ln -s `which gstat` /usr/local/bin/stat
fi
