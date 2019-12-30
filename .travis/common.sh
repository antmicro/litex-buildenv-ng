export IFS="."
read -ra CPU_CONF <<< "$C"
export CPU="${CPU_CONF[0]}"
export CPU_VARIANT="${CPU_CONF[1]}"

export IFS=" "
read -ra TARGET_CONF <<< "$T"

export IFS=""
