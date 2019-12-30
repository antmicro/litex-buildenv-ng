#!/bin/bash

set -e

source .travis/common.sh

for target in "${TARGET_CONF[@]}"; do
	echo "Build: ${C} : ${TC} : ${P} : ${T} : ${F}"
	if [[ -z $F ]]; then
		echo "[FIXME] No firmware provided - skipping..."
	else
		if [[ -z $CPU_VARIANT ]]; then
			python scripts/litex_buildenv_ng.py --cpu $CPU --platform $P --target $target --firmware $F firmware
		else
			python scripts/litex_buildenv_ng.py --cpu $CPU --cpu-variant $CPU_VARIANT --platform $P --target $target --firmware $F firmware
		fi
	fi
done
