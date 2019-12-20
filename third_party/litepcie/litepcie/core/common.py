# This file is Copyright (c) 2015-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

from migen import *

from litepcie.common import *


class LitePCIeSlaveInternalPort:
    def __init__(self, data_width, address_decoder=None):
        self.address_decoder = address_decoder
        self.sink = stream.Endpoint(completion_layout(data_width))
        self.source = stream.Endpoint(request_layout(data_width))


class LitePCIeMasterInternalPort:
    def __init__(self, data_width, channel=None, write_only=False, read_only=False):
        self.channel = channel
        self.write_only = write_only
        self.read_only = read_only
        self.sink = stream.Endpoint(request_layout(data_width))
        self.source = stream.Endpoint(completion_layout(data_width))


class LitePCIeSlavePort:
    def __init__(self, port):
        self.address_decoder = port.address_decoder
        self.sink = port.source
        self.source = port.sink


class LitePCIeMasterPort:
    def __init__(self, port):
        self.channel = port.channel
        self.sink = port.source
        self.source = port.sink
