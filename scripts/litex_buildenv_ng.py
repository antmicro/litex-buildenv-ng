#!/usr/bin/env python3

import argh
import traceback
from log import Log
import config
from prepare import prepare
from gateware_build import gateware
from firmware import firmware


def init_config(args):
    cfg = config.ConfigManager()
    cfg.init(args.env, args.cpu, args.cpu_variant, args.platform, args.target,
             args.firmware)


if __name__ == '__main__':
    parser = argh.ArghParser()
    parser.add_argument("-e",
                        "--env",
                        action="store",
                        default="default",
                        help="Custom environment name")
    parser.add_argument("--cpu", help="cpu name")
    parser.add_argument("--cpu-variant", help="cpu variant")
    parser.add_argument("--platform", help="platform name")
    parser.add_argument("--target", help="setup type")
    parser.add_argument("--firmware", help="target firmware")
    parser.add_argument("--trace",
                        action="store_true",
                        help="dump stack trace on error")
    parser.add_commands([prepare, firmware, gateware])

    options = parser.parse_args()

    try:
        parser.dispatch(pre_call=init_config)
    except Exception as e:
        Log.log(traceback.format_exc())
        Log.log(f"Failed to prepare the environment: {e}")
        if options.trace:
            raise
