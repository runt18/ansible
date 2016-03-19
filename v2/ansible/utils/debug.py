from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import time
import sys

from multiprocessing import Lock

from ansible import constants as C

global_debug_lock = Lock()
def debug(msg):
    if C.DEFAULT_DEBUG:
        global_debug_lock.acquire()
        print("{0:6d} {1:0.5f}: {2!s}".format(os.getpid(), time.time(), msg))
        sys.stdout.flush()
        global_debug_lock.release()
