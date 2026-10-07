import logging
log = logging.getLogger(__name__)

try:
    import plotext as plt
except ImportError:
    plt = None

def plot_charts(stats, width=80, height=20):
    if plt is None:
        log.warning("plotext is not installed. Skipping plotting.")
        return
    if not hasattr(plt, 'plot_size'):
        # plotext 6 replaced the module-level API that runit uses.
        log.warning(
            "plotext %s is not supported (runit needs plotext>=5.3,<6). Skipping plotting.",
            getattr(plt, '__version__', 'unknown'),
        )
        return
    if stats['check_times'] and stats['cpu_percent']:
        try:
            log.info("Plotting charts.")
            start = stats['check_times'][0]
            times = [(t - start).total_seconds() for t in stats['check_times']]
            cpu = stats['cpu_percent']
            from .utils import extract_memory_rss
            rss = extract_memory_rss(stats['memory_info'])
            plt.clear_figure()
            plt.plot_size(width=width, height=height)
            plt.subplots(2, 1)
            plt.subplot(1)
            plt.title("CPU % over time")
            plt.plot(times, cpu, marker='dot')
            if times:
                plt.xticks([times[0], times[-1]])
            plt.ylabel("CPU %")
            plt.subplot(2)
            plt.title("RSS (MB) over time")
            plt.plot(times, [r/1024/1024 for r in rss], marker='dot', color='cyan')
            if times:
                plt.xticks([times[0], times[-1]])
            plt.ylabel("RSS (MB)")
            plt.show()
        except Exception as e:
            log.warning("Could not plot chart: %s", e)
