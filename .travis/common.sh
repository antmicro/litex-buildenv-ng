# Some colors, use it like following;
# echo -e "Hello ${YELLOW}yellow${NC}"
GRAY=' \033[0;30m'
RED=' \033[0;31m'
GREEN=' \033[0;32m'
YELLOW=' \033[0;33m'
PURPLE=' \033[0;35m'
NC='\033[0m' # No Color

SPACER="echo -e ${GRAY} - ${NC}"

if [ $TRAVIS_OS_NAME = 'osx' ]; then
    alias find=gfind
fi

export -f travis_nanoseconds
export -f travis_fold
export -f travis_time_start
export -f travis_time_finish
export -f travis_wait
export -f travis_jigger

if [ $TRAVIS_OS_NAME = 'osx' ]; then
    DATE_SWITCH="-r "
else
    DATE_SWITCH="--date=@"
fi
if [ -z "$DATE_STR" ]; then
	export DATE_TS="$(git log --format=%ct -n1)"
	export DATE_NUM="$(date ${DATE_SWITCH}${DATE_TS} -u +%Y%m%d%H%M%S)"
	export DATE_STR="$(date ${DATE_SWITCH}${DATE_TS} -u +%Y%m%d_%H%M%S)"
	echo "Setting date number to $DATE_NUM"
	echo "Setting date string to $DATE_STR"
fi

function start_section() {
	travis_fold start "$1"
	travis_time_start
	echo -e "${PURPLE}${PACKAGE}${NC}: - $2${NC}"
	echo -e "${GRAY}-------------------------------------------------------------------${NC}"
}

function end_section() {
	echo -e "${GRAY}-------------------------------------------------------------------${NC}"
	travis_time_finish
	travis_fold end "$1"
}

# Disable this warning;
# xxxx/conda_build/environ.py:377: UserWarning: The environment variable
#     'TRAVIS' is being passed through with value 0.  If you are splitting
#     build and test phases with --no-test, please ensure that this value is
#     also set similarly at test time.
export PYTHONWARNINGS=ignore::UserWarning:conda_build.environ

export IFS_BCKUP=$IFS
export IFS="."
read -ra CPU_CONF <<< "$C"
export CPU="${CPU_CONF[0]}"
export CPU_VARIANT="${CPU_CONF[1]}"

export IFS=" "
read -ra TARGET_CONF <<< "$T"

export IFS=$IFS_BCKUP
