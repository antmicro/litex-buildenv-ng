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
SETUP_DIR="$(dirname "${SETUP_SRC}")"
TOP_DIR="$(realpath "${SETUP_DIR}")"

if [ $SOURCED = 0 ]; then
	echo "You must source this script, rather than try and run it."
	echo ". $SETUP_SRC"
	exit 1
fi

# Conda does not support ' ' in the path (it bails early).
if echo "${SETUP_DIR}" | grep -q ' '; then
	echo "You appear to have whitespace characters in the path to this script."
	echo "Please move this repository to another path that does not contain whitespace."
	return 1
fi

# Conda does not support ':' in the path (it fails to install python).
if echo "${SETUP_DIR}" | grep -q ':'; then
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

echo "             This script is: $SETUP_SRC"
echo "         Firmware directory: $TOP_DIR"
echo "         Build directory is: $BUILD_DIR"
echo "     3rd party directory is: $THIRD_DIR"

echo ""
echo "Initializing environment"
echo "---------------------------------"

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

# Install and setup conda for downloading packages
(
	echo
	echo "Installing conda (self contained Python environment with binary package support)"
	if [[ ! -e $CONDA_DIR/bin/conda ]]; then
		cd $BUILD_DIR
		wget --continue https://repo.continuum.io/miniconda/Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh
		chmod a+x Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh
		(
			export HOME=$CONDA_DIR
                        # -p to specify the install location
                        # -b to enable batch mode (no prompts)
                        # -f to not return an error if the location already exists
			./Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh -p $CONDA_DIR -b -f || exit 1
		)
                conda install -y $CONDA_FLAGS python==$PYTHON_VERSION
	fi
    echo "Conda environment ready"

)

echo "Bootstrap bash finished, staring bootstrap.py"

python3 scripts/bootstrap.py
#$@ prepare
