@ECHO off

SET TOP_DIR=%cd%\
SET SETUP_SRC_DIR=%~dp0
SET COPY_FILES=0
SET INITIALIZE_DIR=0
IF NOT %TOP_DIR% == %SETUP_SRC_DIR% (
	SET COPY_FILES=1
)

SET BUILD_DIR=%TOP_DIR%build
SET THIRD_DIR=%TOP_DIR%third_party
SET BUILDENV_LOCAL_TOOLS=%BUILD_DIR%\bin
SET BUILDENV_BUILD_LOG=%BUILD_DIR%\build.log

REM If we activate an enviroment CONDA_PREFIX is set. Otherwise use CONDA_DIR
IF "%CONDA_PREFIX%" == "" (
	SET CONDA_PREFIX=%BUILD_DIR%\conda
)
SET CONDA_DIR=%CONDA_PREFIX%

SET CONDA_VERSION=4.7.10
SET PYTHON_VERSION=3.7

REM Check if path is valid
DIR %TOP_DIR% >>nul || GOTO PATH_FAIL

ECHO ---------------------------------------------------
ECHO      Firmware directory: %TOP_DIR%
ECHO      Build directory is: %BUILD_DIR%
ECHO  3rd party directory is: %THIRD_DIR%
ECHO ---------------------------------------------------
ECHO             Initializing environment
ECHO ---------------------------------------------------

IF NOT EXIST %BUILDENV_LOCAL_TOOLS% (
	MD %BUILDENV_LOCAL_TOOLS%
)

SET PYTHON_PATH=
SET PYTHONHASHSEED=0
SET PYTHONNOUSERSITE=1
SET PYTHONDONTWRITEBYTECODE=1

IF "%SHELL_IS_BUILDENV_READY%" == "" (
	SET "PATH=%BUILDENV_LOCAL_TOOLS%;%CONDA_DIR%;%PATH%"
)

SET CONDA_URI=https://repo.continuum.io/miniconda/Miniconda3-%CONDA_VERSION%-Windows-x86_64.exe
SET CONDA_DEST=Miniconda3.exe

IF NOT EXIST %CONDA_DIR% (
	SET INITIALIZE_DIR=1
    CD %BUILD_DIR%

	ECHO                 Downloading conda
	ECHO ---------------------------------------------------
    powershell /Command "(New-Object System.Net.WebClient).DownloadFile('%CONDA_URI%','%CONDA_DEST%')"
    REM  /D to specify the installation path
    REM  /S to install in silent mode
	ECHO                 Installing conda                     This may take few minutes. Please wait...
	ECHO ---------------------------------------------------
	START /wait "" Miniconda3.exe /S /D=%CONDA_DIR% || GOTO:EOF
	CD ..
)

ECHO                 Call conda activate
ECHO ---------------------------------------------------
CALL "%CONDA_DIR%\Scripts\activate"
IF %INITIALIZE_DIR%==1 (
	IF %COPY_FILES%==1 (
	ECHO     Copying buildenv files to current directory
	ECHO ---------------------------------------------------
	REM Recursive copy excluding 'build' and '.git directories
	ROBOCOPY /S /NJH /NJS /NC /NS /FP /NDL %SETUP_SRC_DIR% %TOP_DIR% /XD build .git
	ECHO ---------------------------------------------------
	)
	python scripts/bootstrap.py
)

ECHO  Bootstrap finished, starting litex_buildenv_ng.py
ECHO ---------------------------------------------------
python scripts/litex_buildenv_ng.py %*% prepare

GOTO:EOF

:PATH_FAIL
ECHO "Path to your current directory appear to have whitespace, ':', or other forbiden characters in it."
ECHO "Please move this repository to another, valid, path."
