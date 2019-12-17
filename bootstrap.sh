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
export CONDA_DIR=$BUILD_DIR/conda
export BUILDENV_LOCAL_TOOLS=$BUILD_DIR/bin
export BUILDENV_BUILD_LOG=$BUILD_DIR/build.log

export CONDA_VERSION=4.7.10
export PYTHON_VERSION=3.7

# If we activate an environment, CONDA_PREFIX is set. Otherwise use CONDA_DIR.
export CONDA_PREFIX="${CONDA_PREFIX:-$CONDA_DIR}"
export CONDA_DIR=$CONDA_PREFIX

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

function pin_conda_package {
	CONDA_PACKAGE_NAME=$1
	CONDA_PACKAGE_VERSION=$2
	echo "Pinning ${CONDA_PACKAGE_NAME} to ${CONDA_PACKAGE_VERSION}"
	CONDA_PIN_FILE=$CONDA_DIR/conda-meta/pinned
	CONDA_PIN_TMP=$CONDA_DIR/conda-meta/pinned.tmp
	touch ${CONDA_PIN_FILE}
	cat ${CONDA_PIN_FILE} | grep -v ${CONDA_PACKAGE_NAME} > ${CONDA_PIN_TMP} || true
	echo "${CONDA_PACKAGE_NAME} ==${CONDA_PACKAGE_VERSION}" >> ${CONDA_PIN_TMP}
	cat ${CONDA_PIN_TMP} | sort > ${CONDA_PIN_FILE}
}

# Install and setup conda for downloading packages
(
	echo
	echo "Installing conda (self contained Python environment with binary package support)"
	if [[ ! -e $CONDA_DIR/bin/conda ]]; then
		cd $BUILD_DIR
		# FIXME: Get the miniconda people to add a "self check" mode
		wget --continue https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
		chmod a+x Miniconda3-latest-Linux-x86_64.sh
		# -p to specify the install location
		# -b to enable batch mode (no prompts)
		# -f to not return an error if the location specified by -p already exists
		(
			export HOME=$CONDA_DIR
			./Miniconda3-latest-Linux-x86_64.sh -p $CONDA_DIR -b -f || exit 1
		)
                pin_conda_package python ${PYTHON_VERSION}
                conda install -y $CONDA_FLAGS python
	fi
    echo "Conda environment ready"

)

echo "Bootstrap bash finished, staring bootstrap.py"

python3 scripts/bootstrap.py 
#$@ prepare
