# This file is Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import time
import argparse
import random as rand
from collections import OrderedDict
from litex import RemoteClient

KB = 1024
MB = 1024*KB
GB = 1024*MB

logical_sector_size = 512


class Timer:
    def __init__(self):
        self.value = None

    def start(self):
        self._start = time.time()

    def stop(self):
        self._stop = time.time()
        self.value = max(self._stop - self._start, 1/1000000)


class LiteSATABISTUnitDriver:
    def __init__(self, regs, constants, name):
        self.regs = regs
        self.name = name
        self.frequency = constants.system_clock_frequency
        self.time = 0
        for s in ["start", "sector", "count", "loops", "random", "done", "aborted", "errors", "cycles"]:
            setattr(self, s, getattr(regs, name + "_" + s))

    def run(self, sector, count, loops, random, blocking=True, hw_timer=True):
        self.sector.write(sector)
        self.count.write(count)
        self.loops.write(loops)
        self.random.write(random)
        timer = Timer()
        timer.start()
        self.start.write(1)
        if blocking:
            while (self.done.read() == 0):
                pass
        timer.stop()
        aborted = self.aborted.read()
        if not aborted:
            if hw_timer:
                self.time = self.cycles.read()/self.frequency
            else:
                self.time = timer.value
            speed = (loops*count*logical_sector_size)/self.time
            errors = self.errors.read()
        else:
            speed = 0
            errors = -1
        return (aborted, errors, speed)


class LiteSATABISTGeneratorDriver(LiteSATABISTUnitDriver):
    def __init__(self, regs, constants, name):
        LiteSATABISTUnitDriver.__init__(self, regs, constants, name + "_generator")


class LiteSATABISTCheckerDriver(LiteSATABISTUnitDriver):
    def __init__(self, regs, constants, name):
        LiteSATABISTUnitDriver.__init__(self, regs, constants,name + "_checker")


class LiteSATABISTIdentifyDriver:
    def __init__(self, regs, constants, name):
        self.regs = regs
        self.name = name
        for s in ["start", "done", "data_width", "source_valid", "source_ready", "source_data"]:
            setattr(self, s, getattr(regs, name + "_identify_" + s))
        self.data = []

    def read_fifo(self):
        self.data = []
        while self.source_valid.read():
            dword = self.source_data.read()
            word_lsb = dword & 0xffff
            word_msb = (dword >> 16) & 0xffff
            self.data += [word_lsb, word_msb]
            self.source_ready.write(1)

    def run(self, blocking=True):
        self.read_fifo()  # flush the fifo before we start
        self.start.write(1)
        if blocking:
            while (self.done.read() == 0):
                pass
            self.read_fifo()
            self.decode()

    def decode(self):
        self.serial_number = ""
        for i, word in enumerate(self.data[10:20]):
            s = word.to_bytes(2, byteorder='big').decode("utf-8")
            self.serial_number += s
        self.firmware_revision = ""
        for i, word in enumerate(self.data[23:27]):
            s = word.to_bytes(2, byteorder='big').decode("utf-8")
            self.firmware_revision += s
        self.model_number = ""
        for i, word in enumerate(self.data[27:46]):
            s = word.to_bytes(2, byteorder='big').decode("utf-8")
            self.model_number += s

        self.total_sectors = self.data[100]
        self.total_sectors += (self.data[101] << 16)
        self.total_sectors += (self.data[102] << 32)
        self.total_sectors += (self.data[103] << 48)

        self.capabilities = OrderedDict()
        self.capabilities["SATA Gen1"] = (self.data[76] >> 1) & 0x1
        self.capabilities["SATA Gen2"] = (self.data[76] >> 2) & 0x1
        self.capabilities["SATA Gen3"] = (self.data[76] >> 3) & 0x1
        self.capabilities["48 bits LBA supported"] = (self.data[83] >> 10) & 0x1

    def hdd_info(self):
        info = "Serial Number: " + self.serial_number + "\n"
        info += "Firmware Revision: " + self.firmware_revision + "\n"
        info += "Model Number: " + self.model_number + "\n"
        info += "Capacity: {:3.2f} GB\n".format((self.total_sectors*logical_sector_size)/GB)
        for k, v in self.capabilities.items():
            info += k + ": " + str(v) + "\n"
        print(info, end="")


def _get_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description="""\
SATA BIST utility.
""")
    parser.add_argument("-s", "--transfer_size", default=1024, help="transfer sizes (in KB, up to 16MB)")
    parser.add_argument("-l", "--total_length", default=256, help="total transfer length (in MB, up to HDD capacity)")
    parser.add_argument("-n", "--loops", default=1, help="number of loop per transfer (allow more precision on speed calculation for small transfers)")
    parser.add_argument("-r", "--random", action="store_true", help="use random data")
    parser.add_argument("-c", "--continuous", action="store_true", help="continuous mode (Escape to exit)")
    parser.add_argument("-i", "--identify", action="store_true", help="only run identify")
    parser.add_argument("-t", "--software_timer", action="store_true", help="use software timer")
    parser.add_argument("-a", "--random_addressing", action="store_true", help="use random addressing")
    parser.add_argument("-d", "--delayed_read", action="store_true", help="read after total length has been written")
    return parser.parse_args()

if __name__ == "__main__":
    args = _get_args()
    wb = RemoteClient()
    wb.open()
    # # #
    identify = LiteSATABISTIdentifyDriver(wb.regs, wb.constants, "sata_bist")
    generator = LiteSATABISTGeneratorDriver(wb.regs, wb.constants, "sata_bist")
    checker = LiteSATABISTCheckerDriver(wb.regs, wb.constants, "sata_bist")

    identify.run()
    identify.hdd_info()

    if not int(args.identify):
        count = int(args.transfer_size)*KB//logical_sector_size
        loops = int(args.loops)
        length = int(args.total_length)*MB
        random = int(args.random)
        continuous = int(args.continuous)
        sw_timer = int(args.software_timer)
        random_addressing = int(args.random_addressing)

        write_and_read_sequence = {"write": 1, "read": 1}
        write_sequence = {"write": 1, "read": 0}
        read_sequence = {"write": 0, "read": 1}
        if int(args.delayed_read):
            sequences = [write_sequence, read_sequence]
        else:
            sequences = [write_and_read_sequence]

        for sequence in sequences:
            sector = 0
            run_sectors = 0
            try:
                while ((run_sectors*logical_sector_size < length) or continuous) and (sector < identify.total_sectors):
                    retry = 0
                    if sequence["write"]:
                        # generator (write data to HDD)
                        write_done = False
                        while not write_done:
                            write_aborted, write_errors, write_speed = generator.run(sector, count, loops, random, True, not sw_timer)
                            write_done = not write_aborted
                            if not write_done:
                                retry += 1
                    else:
                        write_error, write_speed = 0, 0

                    if sequence["read"]:
                        # checker (read and check data from HDD)
                        read_done = False
                        while not read_done:
                            read_aborted, read_errors, read_speed = checker.run(sector, count, loops, random, True, not sw_timer)
                            read_done = not read_aborted
                            if not read_done:
                                retry += 1
                    else:
                        read_errors, read_speed = 0, 0

                    ratio = identify.data_width.read()//32
                    print("sector={:d} wr_speed={:4.2f}MB/s rd_speed={:4.2f}MB/s errors={:d} retry={:d} ({:d}MB)".format(
                        sector,
                        write_speed/MB*ratio,
                        read_speed/MB*ratio,
                        write_errors + read_errors,
                        retry,
                        int(run_sectors*logical_sector_size/MB)*ratio))
                    if random_addressing:
                        sector = rand.randint(0, identify.total_sectors//(256*2))*256
                    else:
                        sector += count
                    run_sectors += count

            except KeyboardInterrupt:
                pass
    # # #
    wb.close()
