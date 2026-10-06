import sys
from .monitor import monitor_process
from .report import format_report
from .plotting import plot_charts
from .utils import strip_ansi
from .logging_config import setup_logging
import argparse
import logging
from contextlib import redirect_stdout
from io import StringIO


def exit_status(returncode):
    """Map a subprocess return code to the exit status runit should use.

    A program killed by signal N has a negative return code; shells report
    that as 128 + N, so runit does the same.
    """
    if returncode is None:
        return 1
    if returncode < 0:
        return 128 - returncode
    return returncode


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
    except PermissionError as e:
        log.error("Command cannot be executed: %s (%s)", args.command[0], e)
        return 126
    report = format_report(stats)
    if args.out_file:
        # Capture the report and charts, then show them and write the file.
        buf = StringIO()
        with redirect_stdout(buf):
            if args.plot:
                plot_charts(stats, args.plot_width, args.plot_height)
            print(report)
        output = buf.getvalue()
        sys.stdout.write(output)
        sys.stdout.flush()
        file_output = output
        if getattr(args, 'strip_ansi', False):
            log.info("Stripping ANSI codes for output file.")
            file_output = strip_ansi(output)
        with open(args.out_file, 'w', encoding='utf-8') as f:
            f.write(file_output)
        log.info("Wrote output to file: %s", args.out_file)
    else:
        if args.plot:
            plot_charts(stats, args.plot_width, args.plot_height)
        print(report)
    log.info("runit CLI finished.")
    return exit_status(stats.get('returncode'))

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
