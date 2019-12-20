#!/bin/bash

if [ "`whoami`" = "root" ]
then
    echo "Running the script as root is not permitted"
    return 1 2> /dev/null || exit 1
fi

if [ ! -n "$BASH_VERSION" ]; then
    echo "This script has to be sourced in bash"
    return 1 2> /dev/null || exit 1
fi

[[ "${BASH_SOURCE[0]}" != "${0}" ]] && SOURCED=1 || SOURCED=0

SETUP_SRC="$(realpath ${BASH_SOURCE[0]})"
SETUP_SRC_DIR="$(dirname "${SETUP_SRC}")"
SCRIPT_DIR="$(realpath "${SETUP_SRC_DIR}")"
TOP_DIR="$(pwd)"
COPY_FILES=0
if [ ! "$TOP_DIR" == "$(realpath "${SETUP_DIR}")" ]; then
    COPY_FILES=1
fi

if [ $SOURCED = 0 ]; then
	echo "You must source this script, rather than try and run it."
	echo ". $SETUP_SRC"
	exit 1
fi

# Conda does not support ' ' in the path (it bails early).
if echo "${TOP_DIR}" | grep -q ' '; then
	echo "You appear to have whitespace characters in the path to this script."
	echo "Please move this repository to another path that does not contain whitespace."
	return 1
fi

# Conda does not support ':' in the path (it fails to install python).
if echo "${TOP_DIR}" | grep -q ':'; then
	echo "You appear to have ':' characters in the path to this script."
	echo "Please move this repository to another path that does not contain this character."
	return 1
fi

export BUILD_DIR=$TOP_DIR/build
export THIRD_DIR=$TOP_DIR/third_party
export BUILDENV_LOCAL_TOOLS=$BUILD_DIR/bin
export BUILDENV_BUILD_LOG=$BUILD_DIR/build.log

# If we activate an environment, CONDA_PREFIX is set. Otherwise use CONDA_DIR.
export CONDA_PREFIX="${CONDA_PREFIX:-$BUILD_DIR/conda}"
export CONDA_DIR=$CONDA_PREFIX

export CONDA_VERSION=4.7.10
export PYTHON_VERSION=3.7

echo "---------------------------------------------------"
echo "     Firmware directory: $TOP_DIR"
echo "     Build directory is: $BUILD_DIR"
echo " 3rd party directory is: $THIRD_DIR"

echo "---------------------------------------------------"
echo "             Initializing environment"
echo "---------------------------------------------------"

mkdir -p $BUILDENV_LOCAL_TOOLS

unset PYTHONPATH
export PYTHONHASHSEED=0
export PYTHONNOUSERSITE=1
export PYTHONDONTWRITEBYTECODE=1

if [ -z "$SHELL_IS_BUILDENV_READY" ]
then
    # Install and setup conda for downloading packages
    export PATH=$BUILDENV_LOCAL_TOOLS:$CONDA_DIR/bin:$PATH:/sbin
fi

if [ "$(uname)" == "Linux" ] ; then
    CONDA_INSTALLER=Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh
else
    CONDA_INSTALLER=Miniconda3-${CONDA_VERSION}-MacOSX-x86_64.sh
fi

# Install conda for downloading packages
(
	if [[ ! -e $CONDA_DIR/bin/conda ]]; then
		cd $BUILD_DIR
        echo "                Downloading conda"
        echo "---------------------------------------------------"
		wget --continue https://repo.continuum.io/miniconda/$CONDA_INSTALLER
		chmod a+x $CONDA_INSTALLER
        echo "                 Installing conda"
        echo "---------------------------------------------------"
        # -p to specify the install location
        # -b to enable batch mode (no prompts)
        # -f to not return an error if the location already exists
        ./$CONDA_INSTALLER -p $CONDA_DIR -b -f || exit 1
        cd ..
	fi
)

if [ $COPY_FILES -eq 1 ]; then
    echo "    Copying buildenv files to current directory"
    echo "---------------------------------------------------"
    cp -r $SCRIPT_DIR/* .
fi

python3 scripts/bootstrap.py 
echo " Bootstrap finished, staring litex_buildenv_ng.py"
echo "---------------------------------------------------"
python3 scripts/litex_buildenv_ng.py $@ prepare
