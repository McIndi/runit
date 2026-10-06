import sys
from .monitor import monitor_process
from .report import format_report
from .plotting import plot_charts
from .utils import strip_ansi, exit_status
from .logging_config import setup_logging
import argparse
import logging
import os
from contextlib import redirect_stdout
from io import StringIO


def _write_stdout(text, log):
    """Write the report to stdout. Return False if stdout is closed or broken.

    When the reader has gone away (for example `runit cmd | head`), stay quiet
    like other command line tools. For other errors (for example a full disk),
    log one line. In both cases stdout is pointed at os.devnull, so that the
    flush at interpreter exit does not raise again.
    """
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
        return True
    except (OSError, ValueError) as e:
        if isinstance(e, BrokenPipeError):
            log.info("Output reader closed the pipe; report not shown.")
        else:
            log.error("Cannot write the report to stdout: %s", e)
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            os.close(devnull)
        except (OSError, ValueError):
            pass
        return False


def run_cli():
    parser = create_parser()
    args = parser.parse_args()
    setup_logging(args.log_level)
    log = logging.getLogger(__name__)
    log.info("Starting runit CLI")
    if not args.command:
        parser.print_help()
        log.info("No command provided. Exiting.")
        return 0
    try:
        # The program's stdout and stderr go to the terminal as it runs.
        stats = monitor_process(args.command)
    except FileNotFoundError as e:
        log.error("Command not found: %s (%s)", args.command[0], e)
        return 127
    except OSError as e:
        # For example EACCES, or ENOEXEC for a script without a shebang.
        log.error("Command cannot be executed: %s (%s)", args.command[0], e)
        return 126
    status = exit_status(stats.get('returncode'))
    report = format_report(stats)
    # Capture the report and charts, write --out-file first, then the terminal.
    buf = StringIO()
    with redirect_stdout(buf):
        if args.plot:
            plot_charts(stats, args.plot_width, args.plot_height)
        print(report)
    output = buf.getvalue()
    if args.out_file:
        file_output = output
        if getattr(args, 'strip_ansi', False):
            log.info("Stripping ANSI codes for output file.")
            file_output = strip_ansi(output)
        try:
            with open(args.out_file, 'w', encoding='utf-8') as f:
                f.write(file_output)
            log.info("Wrote output to file: %s", args.out_file)
        except OSError as e:
            # runit's own job failed: report it in one line. A non-zero
            # exit code of the command wins; otherwise runit exits 1.
            log.error("Cannot write --out-file %s: %s", args.out_file, e)
            if status == 0:
                status = 1
    _write_stdout(output, log)
    log.info("runit CLI finished.")
    return status

def create_parser():
    parser = argparse.ArgumentParser(
        description="Run a command and report on its execution (time, resources, etc)."
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set the logging level (default: INFO)'
    )
    parser.add_argument(
        '--out-file',
        type=str,
        default=None,
        help='Also write the report (and charts) to this file. '
             'The program output and the report are still shown in the terminal.'
    )
    parser.add_argument(
        '--strip-ansi',
        action='store_true',
        help='Remove ANSI escape codes from output (for plain text files).'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Show resource usage charts (requires plotext).'
    )
    parser.add_argument(
        '--plot-width',
        type=int,
        default=80,
        help='Set the plot width (default: 80)'
    )
    parser.add_argument(
        '--plot-height',
        type=int,
        default=20,
        help='Set the plot height (default: 20)'
    )
    parser.add_argument(
        'command',
        nargs=argparse.REMAINDER,
        help='The command and arguments to run.'
    )
    return parser
