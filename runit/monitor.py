import subprocess
import psutil
from datetime import datetime
import time
import logging
import threading
import sys

log = logging.getLogger(__name__)
_STREAM_CHUNK_SIZE = 4096
_THREAD_JOIN_TIMEOUT_SECONDS = 5

def _binary_writer(target):
    """Return a function that writes bytes to ``target`` and flushes it.

    ``target`` is normally ``sys.stdout`` or ``sys.stderr``. A text stream
    without a binary ``buffer`` (for example ``io.StringIO``) gets the bytes
    decoded, so that forwarding never fails because of the stream type.
    """
    buffer = getattr(target, 'buffer', None)
    if buffer is not None:
        def write(chunk):
            buffer.write(chunk)
            buffer.flush()
    else:
        def write(chunk):
            target.write(chunk.decode(errors='backslashreplace'))
            target.flush()
    return write

def _start_proc(command: list):
    log.info("Starting process: %s", command)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return proc

def monitor_process(command):
    log.info("Monitoring process: %s", command)
    stats = {
        'start_time': datetime.now(),
        'command': command,
        'check_times': [],
        'cpu_percent': [],
        'memory_info': [],
        'children': [],
        'threads': [],
        'stdout': '',
        'stderr': '',
        'returncode': None,
    }
    proc = _start_proc(command)
    ps_proc = psutil.Process(proc.pid)
    log.debug("Subprocess started with PID %s", ps_proc.pid)

    stdout_chunks = []
    stderr_chunks = []

    def _safe_close(stream):
        try:
            stream.close()
        except (OSError, ValueError):
            pass

    def _forward_and_capture(stream, target, chunks):
        reader = getattr(stream, 'read1', None)
        if reader is None:
            # Fallback for file-like streams that do not implement read1().
            reader = stream.read
        write = _binary_writer(target)
        try:
            while True:
                chunk = reader(_STREAM_CHUNK_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
                if write is None:
                    continue
                try:
                    write(chunk)
                except (OSError, ValueError):
                    # The destination is closed (for example EPIPE). Close
                    # the pipe so the program sees the same closed pipe.
                    raise
                except Exception as e:
                    # Any other failure must not stop the reader: a program
                    # that cannot write blocks on a full pipe or is killed by
                    # a closed one. Keep capturing and stop forwarding.
                    log.warning("Stream forwarding stopped due to write error: %s", e)
                    write = None
        except (OSError, ValueError) as e:
            log.warning("Stream forwarding stopped due to I/O error: %s", e)
        finally:
            _safe_close(stream)

    stdout_thread = threading.Thread(
        target=_forward_and_capture,
        args=(proc.stdout, sys.stdout, stdout_chunks),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_forward_and_capture,
        args=(proc.stderr, sys.stderr, stderr_chunks),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    stats['pid'] = ps_proc.pid
    try:
        while ps_proc.is_running() and not ps_proc.status() == psutil.STATUS_ZOMBIE:
            try:
                cpu_percent = ps_proc.cpu_percent(interval=0.1)
                memory_info = ps_proc.memory_info()
                children = ps_proc.children(recursive=True)
                threads = ps_proc.threads()
                stats['cpu_percent'].append(cpu_percent)
                stats['memory_info'].append(memory_info)
                stats['children'].append(children)
                stats['threads'].append(threads)
                stats['check_times'].append(datetime.now())
                log.debug("Sampled stats at %s, CPU: %s%%, Memory: %s bytes, Children: %s, Threads: %s", stats['check_times'][-1], cpu_percent, memory_info.rss, len(children), len(threads))
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
                log.warning("Process ended or became inaccessible during monitoring.")
                break
            time.sleep(0.1)
        stats['returncode'] = proc.wait()
        stdout_thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
        stderr_thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
        if stdout_thread.is_alive() or stderr_thread.is_alive():
            log.warning("Timed out waiting for stream forwarding threads to finish.")
            for stream in (proc.stdout, proc.stderr):
                _safe_close(stream)
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
        # Preserve undecodable bytes in a visible form without dropping content.
        stats['stdout'] = b''.join(stdout_chunks).decode(errors='backslashreplace')
        stats['stderr'] = b''.join(stderr_chunks).decode(errors='backslashreplace')

    except Exception as e:
        log.warning("Exception during stat collection: %s", e)
    if stats['returncode'] is None:
        stats['returncode'] = proc.wait()
    stats['end_time'] = datetime.now()
    stats['duration'] = stats['end_time'] - stats['start_time']
    log.info("Process monitoring complete. Duration: %s", stats['duration'])
    return stats
