from .utils import extract_memory_rss, extract_num_threads, extract_num_children, describe_exit
import logging

log = logging.getLogger(__name__)

def format_report(stats):
    log.info("Formatting report.")
    rss_values = extract_memory_rss(stats['memory_info'])
    num_threads = extract_num_threads(stats['threads'])
    num_children = extract_num_children(stats['children'])
    report = [
        "Command: {}".format(stats['command']),
        "PID: {}".format(stats.get('pid')),
        "Start Time: {}".format(stats['start_time']),
        "End Time: {}".format(stats['end_time']),
        "Duration: {}".format(stats['duration']),
        "Exit Code: {}".format(describe_exit(stats.get('returncode'))),
        "Max RSS (bytes): {}".format(max(rss_values) if rss_values else 'N/A'),
        "Max Threads: {}".format(max(num_threads) if num_threads else 'N/A'),
        "Max Children: {}".format(max(num_children) if num_children else 'N/A'),
        "Samples: {}".format(len(stats['check_times'])),
        "\nstdout: \n\n\t{}".format('\n\t'.join(stats['stdout'].splitlines()) if stats['stdout'] else 'N/A'),
        "\nstderr: \n\n\t{}".format('\n\t'.join(stats['stderr'].splitlines()) if stats['stderr'] else 'N/A'),

    ]
    return "\n=== runit report ===\n" + "\n".join(report)
