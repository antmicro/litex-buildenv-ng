#!/bin/bash

set -e

source .travis/common.sh

for target in "${TARGET_CONF[@]}"; do
	echo -e "${PURPLE}[BUILD] CPU: ${C} | Toolchain: ${TC} | Platform: ${P} | Target: ${T} | Firmware: ${F}${NC}"
	$SPACER
	if [[ -z $CPU_VARIANT ]]; then
		python3 scripts/litex_buildenv_ng.py --cpu $CPU --platform $P --target $target --firmware $F firmware
		exit $?
		# [XXX] Add gateware build
	else
		python3 scripts/litex_buildenv_ng.py --cpu $CPU --cpu-variant $CPU_VARIANT --platform $P --target $target --firmware $F firmware
		# [XXX] Add gateware build
		exit $?
	fi
done

