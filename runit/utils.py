import re
import logging
import signal
from ast import literal_eval

log = logging.getLogger(__name__)

def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

def exit_status(returncode):
    """Map a subprocess return code to the exit status runit uses.

    A program killed by signal N has a negative return code; shells report
    that as 128 + N, so runit does the same.
    """
    if returncode is None:
        return 1
    if returncode < 0:
        return 128 - returncode
    return returncode

def describe_exit(returncode):
    """Text for the report: runit's exit status, plus the signal if there was one."""
    status = exit_status(returncode)
    if returncode is None or returncode >= 0:
        return str(status)
    try:
        name = signal.Signals(-returncode).name
    except ValueError:
        return "{} (signal {})".format(status, -returncode)
    return "{} (signal {}, {})".format(status, -returncode, name)

def extract_memory_rss(memory_info_list):
    log.debug("Extracting memory RSS values.")
    rss_values = []
    for mem in memory_info_list:
        try:
            if isinstance(mem, str):
                mem = literal_eval(mem)
            rss = getattr(mem, 'rss', None)
            if rss is not None:
                rss_values.append(rss)
        except Exception:
            log.debug("Failed to extract RSS from memory info entry.")
            continue
    return rss_values

def extract_num_threads(threads_list):
    log.debug("Extracting number of threads per sample.")
    return [len(t) if hasattr(t, '__len__') else 0 for t in threads_list]

def extract_num_children(children_list):
    log.debug("Extracting number of children per sample.")
    return [len(c) if hasattr(c, '__len__') else 0 for c in children_list]
