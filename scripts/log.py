import os


class Log:

    _log = open(os.getenv("BUILDENV_BUILD_LOG"), "w")

    @staticmethod
    def log(arg):
        s = str(arg)
        print(s)
        Log._log.write(s)

    @staticmethod
    def dump():
        with open(os.getenv("BUILDENV_BUILD_LOG"), "r+") as log_read:
            return log_read.read()
