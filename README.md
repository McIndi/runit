# runit

A Python CLI tool to execute, monitor, and profile and visualize commands.

## Project Purpose

This project was created to prove that advanced functionality is absolutely possible in the terminal. `runit` showcases real-time monitoring of child processes, delivers detailed resource reports, and is built with a strong emphasis on robust, well-tested code. The goal: bring a modern, delightful CLI experience to profiling command execution with charts and everything.

## License

GPL v3. Please see the LICENSE file in the root of the repo for details.

## Features

- Utilizes [psutil](https://pypi.org/project/psutil/) for advanced resource tracking
- Reports execution time, system resource usage, threads, and child processes (including monitoring of all children)
- Terminal charts displaying CPU and memory usage
- Well tested

## Demo

See `runit` in action:

![runit demo](assets/runit-demo.gif)

## Requirements
* Python 3.9+
* psutil
* plotext 5.x (`plotext>=5.3,<6`). plotext 6 replaced the plotting API that runit uses, so it is not supported yet.

## Installation

Clone this repository and install with pip:

```sh
git clone https://github.com/notesofcliff/runit.git
cd runit
python -m venv .venv
source .venv/bin/activate  # Or (for Windows) .venv/Scripts/activate
pip install -e .
# Optionally run the tests
python test.py

```

Or, install directly from GitHub:

```sh
pip install git+https://github.com/notesofcliff/runit.git
```

After installation, use `runit` to run and analyze any command:

```sh
runit [args...] <command>
```

For example:

```sh
runit echo hello world
```

* If you run `runit` with no arguments, it will print help.

You'll receive a detailed resource usage report.

If [plotext](https://pypi.org/project/plotext/) is installed and `--plot` is specified, terminal charts for CPU and memory usage over time will be displayed.

* Charts appear only if the child process runs long enough to gather data.

## Example Output

```shell
=== runit report ===
Command: ['python', '-c', 'print(123)']
PID: 12345
Start Time: 2025-07-31 12:00:00.000000
End Time: 2025-07-31 12:00:01.000000
Duration: 0:00:01
Exit Code: 0
Max RSS (bytes): 12345678
Max Threads: 4
Max Children: 0
Samples: 10
```

If plotext is installed, you'll also see beautiful terminal charts for CPU and memory usage.

## Run the Benchmarks

To run the benchmarks:

```sh
runit python benchmark.py
```

## CLI Options

- `--log-level LEVEL`: Set the logging level (default: INFO)
- `--out-file FILE`: Also write the report and charts to a file (they are still shown in the terminal)
- `--strip-ansi`: Remove ANSI escape codes from output file (for plain text files)
- `--plot`: If specified, attempt to plot CPU and memory usage
- `--plot-width N`, `--plot-height N`: Set the chart size (default: 80 x 20)
- `command`: The command to run and monitor

The output of the command goes to the terminal while it runs (stdout to stdout, stderr to stderr), with or without `--out-file`. When the command ends, runit shows the report, which also contains the captured stdout and stderr.

When using `--out-file`, the report and charts are both displayed in the terminal and written to the file. For plain text (no colors or terminal formatting), simply add `--strip-ansi`.

```sh
runit --out-file out.txt --strip-ansi python benchmark.py
```

You'll see the report and charts in your terminal, and a plain text version in `out.txt`.

## Exit Status

runit exits with the exit code of the command, so you can use it in scripts and CI:

- The exit code of the command (for example, `runit false` exits with 1).
- 128 + N when the command is stopped by signal N (for example, 143 for SIGTERM).
- 127 when the command is not found, and 126 when it cannot be executed (for example, no permission, or a script without a `#!` line).

The `Exit Code:` line of the report shows the same value that runit exits with. For a signal, it also shows the signal, for example `Exit Code: 143 (signal 15, SIGTERM)`.

If runit cannot write the `--out-file` file, it logs one error line. If the command failed, runit exits with the exit code of the command; if the command exited with 0, runit exits with 1. If runit cannot write the report to stdout (for example, a full disk), it logs one error line and exits with the exit code of the command. If the reader of stdout goes away (for example, `runit yes | head`), runit stops quietly. The `--out-file` file is written before the report goes to the terminal.

This behavior is new in 0.2.0. Releases up to 0.1.4 always exited with 0. If a script relies on that, use `runit ... || true`.

## Development & Extending

### Project Structure

The codebase is organized for clarity and extensibility:

```
runit/
├── __init__.py
├── cli.py             # CLI handling: argparse setup and entrypoint
├── monitor.py         # Process launching + stat collection logic
├── report.py          # Summary formatter (text output)
├── plotting.py        # CPU/memory plots via plotext
├── utils.py           # Reusable helpers (ANSI stripping, extractors)
└── logging_config.py  # Centralized logging setup
```

### How to Add Features or Extend

- **Add new measurements:**
  - Extend `monitor.py` to collect additional stats.
  - Add new extractors to `utils.py`.
- **Change reporting:**
  - Update or add new formatters in `report.py`.
- **Add new CLI options:**
  - Edit `cli.py` and its `create_parser()` function.
- **Add/modify plotting:**
  - Update `plotting.py` (plotting is optional and gracefully degrades if `plotext` is missing).
- **Logging:**
  - All modules use a named logger for granular control. Adjust logging config in `logging_config.py`.
runit --out-file out.txt --strip-ansi python benchmark.py

### Tips for Contributors

- Each module should do one thing (separation of concerns).
- Avoid global state; keep functions pure where possible.
- Add tests for new features in `test.py`.
- Use dependency injection for flexibility (e.g., pass formatters or flags).
- Optional features should degrade gracefully (never crash if a dependency is missing).
