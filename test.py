import subprocess
import unittest
import tempfile
import os
import re
import signal
import sys
import time

class TestRunitCLI(unittest.TestCase):
    """Integration tests for the runit CLI command."""

    def test_nonexistent_command(self):
        """Fails gracefully when a nonexistent command is run."""
        result = subprocess.run(['runit', 'nonexistent_command_12345'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue('error' in result.stderr.lower() or 'not found' in result.stderr.lower() or result.returncode != 0)

    def test_quick_exit_command(self):
        """Handles a process that exits almost instantly."""
        result = subprocess.run(['runit', 'python', '-c', 'pass'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Command:', result.stdout)

    def test_output_file_overwrite(self):
        """Ensures output file is overwritten on repeated runs."""
        out_file = 'test_runit_out_overwrite.txt'
        try:
            for i in range(2):
                result = subprocess.run([
                    'runit', '--out-file', out_file, 'python', '-c', f'print({i})'
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('Command:', file_content)
            self.assertIn('print(1)', file_content)
        finally:
            if os.path.exists(out_file):
                os.remove(out_file)

    def test_argument_parsing(self):
        """Checks that CLI options like log level and plot are parsed."""
        result = subprocess.run(['runit', '--log-level', 'DEBUG', '--plot', 'python', '-c', 'print(123)'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Command:', result.stdout)

    def test_plotting_graceful_degradation(self):
        """Verifies plotting does not crash if plotext is missing."""
        result = subprocess.run(['runit', '--plot', 'python', '-c', 'print(123)'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Command:', result.stdout)

    def test_no_arguments_prints_help(self):
        """Shows help when no arguments are provided."""
        result = subprocess.run(['runit'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue('usage:' in result.stdout.lower() or 'usage:' in result.stderr.lower())

    def test_command_runs_and_reports(self):
        """Runs a command and checks for key report fields."""
        result = subprocess.run(['runit', 'python', '-c', 'print(123)'], capture_output=True, text=True)
        out = result.stdout
        self.assertEqual(result.returncode, 0)
        self.assertIn('Command:', out)
        self.assertIn('Start Time:', out)
        self.assertIn('End Time:', out)
        self.assertIn('Max RSS (bytes):', out)
        self.assertIn('Max Threads:', out)
        self.assertIn('Max Children:', out)
        self.assertIn('Samples:', out)

    def test_streams_output_in_real_time(self):
        """Streams child output before command completion."""
        max_first_output_delay_seconds = 1.5
        code = 'import time; print("stream-now", flush=True); time.sleep(2); print("done", flush=True)'
        proc = subprocess.Popen(
            ['runit', 'python', '-c', code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            start = time.monotonic()
            first_line = proc.stdout.readline().strip()
            elapsed = time.monotonic() - start

            self.assertEqual(first_line, 'stream-now')
            self.assertLess(elapsed, max_first_output_delay_seconds)

            stdout, stderr = proc.communicate(timeout=10)
            self.assertEqual(proc.returncode, 0, msg=stderr)
            self.assertIn('Command:', stdout)
            self.assertIn('End Time:', stdout)
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=5)

    def test_out_file_and_strip_ansi(self):
        """Checks --out-file and --strip-ansi produce plain text output."""
        out_file = 'test_runit_out.txt'
        try:
            result = subprocess.run([
                'runit', '--out-file', out_file, '--strip-ansi', 'python', '-c', 'print(123)'
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            # Output should be in terminal (stdout)
            self.assertIn('Command:', result.stdout)
            # File should exist and contain plain text
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('Command:', file_content)
            # Should not contain ANSI escape codes
            ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
            self.assertIsNone(ansi_escape.search(file_content))
        finally:
            if os.path.exists(out_file):
                os.remove(out_file)

class TestStatExtractors(unittest.TestCase):
    """Unit tests for stat extraction utility functions."""

    def test_strip_ansi(self):
        """Removes ANSI codes from a string as expected."""
        from runit.utils import strip_ansi
        ansi_text = '\x1b[31mRed\x1b[0m Normal \x1b[1;32mGreenBold\x1b[0m'
        plain = strip_ansi(ansi_text)
        self.assertIn('Red', plain)
        self.assertIn('Normal', plain)
        self.assertIn('GreenBold', plain)
        self.assertNotIn('\x1b', plain)

    def test_extract_memory_rss(self):
        """Extracts RSS values from memory info objects."""
        from runit.utils import extract_memory_rss
        class DummyMem:
            def __init__(self, rss): self.rss = rss
        mem_list = [DummyMem(100), DummyMem(200), DummyMem(150)]
        self.assertEqual(extract_memory_rss(mem_list), [100, 200, 150])

    def test_extract_num_threads(self):
        """Counts threads in each sample correctly."""
        from runit.utils import extract_num_threads
        threads_list = [[1,2,3], [1,2], []]
        self.assertEqual(extract_num_threads(threads_list), [3,2,0])

    def test_extract_num_children(self):
        """Counts child processes in each sample correctly."""
        from runit.utils import extract_num_children
        children_list = [[1], [], [1,2,3]]
        self.assertEqual(extract_num_children(children_list), [1,0,3])

class TestRunitAccuracy(unittest.TestCase):
    def test_child_process_monitoring(self):
        """Runs a command that spawns child processes and checks Max Children > 0."""
        code = "import subprocess; subprocess.run(['sleep', '5'])"
        result = subprocess.run(['runit', 'python', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Max Children:', result.stdout)
        # Should be at least 1 child
        lines = result.stdout.splitlines()
        for line in lines:
            if line.strip().startswith('Max Children:'):
                val = int(line.split(':')[1].strip())
                self.assertGreaterEqual(val, 1)

    def test_long_running_command_sampling(self):
        """Runs a command that sleeps and checks for multiple samples."""
        result = subprocess.run(['runit', 'python', '-c', 'import time; time.sleep(2)'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Samples:', result.stdout)
        # Should be more than 1 sample
        lines = result.stdout.splitlines()
        for line in lines:
            if line.strip().startswith('Samples:'):
                val = int(line.split(':')[1].strip())
                self.assertGreater(val, 1)

    def test_thread_count_accuracy(self):
        """Runs a command that spawns threads and checks Max Threads > 1."""
        code = "import time;import threading; [threading.Thread(target=lambda:time.sleep(1)).start() for _ in range(3)];"
        result = subprocess.run(['runit', 'python', '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Max Threads:', result.stdout)
        lines = result.stdout.splitlines()
        for line in lines:
            if line.strip().startswith('Max Threads:'):
                val = int(line.split(':')[1].strip())
                self.assertGreaterEqual(val, 3)

    def test_output_file_error_handling(self):
        """Tries to write to a read-only location: one-line error, command's exit code kept."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ro_dir = os.path.join(tmpdir, 'ro')
            os.mkdir(ro_dir)
            os.chmod(ro_dir, 0o555)  # read-only
            out_file = os.path.join(ro_dir, 'out.txt')
            result = subprocess.run(['runit', '--out-file', out_file, 'python', '-c', 'print(123); raise SystemExit(3)'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 3)
            self.assertTrue('error' in result.stderr.lower() or 'permission' in result.stderr.lower())
            self.assertNotIn('Traceback', result.stderr)
            self.assertIn('Exit Code: 3', result.stdout)

    def test_malformed_cli_arguments(self):
        """Passes invalid CLI options and checks for error/help output."""
        result = subprocess.run(['runit', '--not-an-option'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue('usage:' in result.stdout.lower() or 'usage:' in result.stderr.lower())

    def test_unicode_output_handling(self):
        """Runs a command that prints Unicode and checks report and output file."""
        out_file = 'test_runit_unicode.txt'
        try:
            result = subprocess.run(['runit', '--out-file', out_file, 'python', '-c', 'print("✓ ü ñ")'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn('✓', result.stdout)
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('✓', file_content)
        finally:
            if os.path.exists(out_file):
                os.remove(out_file)

    def test_resource_chart_output(self):
        """If plotext is installed, --plot should produce chart output."""
        # This test is best-effort: checks for chart-like output
        result = subprocess.run(['runit', '--plot', 'python', '-c', 'import time; time.sleep(1)'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        # Look for plotext chart markers (e.g., 'CPU Usage', 'Memory Usage')
        self.assertTrue(r'CPU % over time' in result.stdout or 'RSS (MB) over time' in result.stdout or 'plotext' in result.stdout)


class TestRunitRegressions(unittest.TestCase):
    """Regression tests that run the installed ``runit`` entrypoint."""

    # Generous limit so that a hang fails the test instead of blocking CI.
    TIMEOUT_SECONDS = 60
    # Well above the ~64 KB pipe buffer that made 0.1.4 hang.
    LARGE_OUTPUT_BYTES = 1024 * 1024

    def _run(self, args, timeout=None, text=True):
        return subprocess.run(
            ['runit', '--log-level', 'WARNING'] + args,
            capture_output=True,
            text=text,
            timeout=timeout or self.TIMEOUT_SECONDS,
        )

    def _large_output_code(self, stream):
        return (
            'import sys\n'
            'for i in range({n}):\n'
            '    sys.{stream}.write("line %07d\\n" % i)\n'
        ).format(n=self.LARGE_OUTPUT_BYTES // 13, stream=stream)

    def _expected_large_output(self):
        return ''.join('line %07d\n' % i for i in range(self.LARGE_OUTPUT_BYTES // 13))

    def test_out_file_keeps_streaming_after_first_chunk(self):
        """--out-file must not crash the forwarder or kill the program."""
        code = (
            'import time\n'
            'print("first", flush=True)\n'
            'time.sleep(0.5)\n'
            'for i in range(3):\n'
            '    print("later-%d" % i, flush=True)\n'
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, 'out.txt')
            result = self._run(['--out-file', out_file, sys.executable, '-c', code])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertNotIn('BrokenPipeError', result.stderr)
            self.assertTrue(
                result.stdout.startswith('first\nlater-0\nlater-1\nlater-2\n'),
                msg=result.stdout[:500],
            )
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('Command:', file_content)
            for line in ('first', 'later-0', 'later-1', 'later-2'):
                self.assertIn(line, file_content)
            self.assertNotIn('BrokenPipeError', file_content)

    def test_out_file_with_large_output(self):
        """--out-file with more than a pipe buffer of output completes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, 'out.txt')
            result = self._run(['--out-file', out_file, sys.executable, '-c',
                                self._large_output_code('stdout')])
            self.assertEqual(result.returncode, 0, msg=result.stderr[-2000:])
            expected = self._expected_large_output()
            self.assertTrue(result.stdout.startswith(expected))
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('Command:', file_content)
            last_line = expected.splitlines()[-1]
            self.assertIn(last_line, file_content)

    def test_out_file_with_plot_and_strip_ansi(self):
        """Charts are written to --out-file and ANSI codes are removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, 'out.txt')
            result = self._run(['--out-file', out_file, '--strip-ansi', '--plot',
                                sys.executable, '-c', 'import time; time.sleep(1)'])
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('CPU % over time', file_content)
            self.assertIn('Command:', file_content)
            self.assertIsNone(re.search(r'\x1B\[[0-?]*[ -/]*[@-~]', file_content))

    def test_large_stdout_does_not_hang(self):
        """More than 64 KB of stdout is forwarded in full without hanging."""
        result = self._run([sys.executable, '-c', self._large_output_code('stdout')])
        self.assertEqual(result.returncode, 0, msg=result.stderr[-2000:])
        self.assertTrue(result.stdout.startswith(self._expected_large_output()))
        self.assertIn('Command:', result.stdout)

    def test_large_stderr_does_not_hang(self):
        """More than 64 KB of stderr is forwarded in full without hanging."""
        result = self._run([sys.executable, '-c', self._large_output_code('stderr')])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stderr.startswith(self._expected_large_output()))
        self.assertIn('Command:', result.stdout)

    def test_exit_code_is_propagated(self):
        """runit exits with the exit code of the program it ran."""
        result = self._run([sys.executable, '-c', 'import sys; sys.exit(3)'])
        self.assertEqual(result.returncode, 3, msg=result.stderr)
        self.assertIn('Exit Code: 3', result.stdout)

    @unittest.skipIf(os.name != 'posix', 'POSIX signals only')
    def test_signal_exit_code_is_propagated(self):
        """A program killed by a signal gives the shell-style 128+N exit code."""
        code = 'import os, signal; os.kill(os.getpid(), signal.SIGTERM)'
        result = self._run([sys.executable, '-c', code])
        self.assertEqual(result.returncode, 128 + signal.SIGTERM, msg=result.stderr)
        # The report shows the same value that runit exits with.
        self.assertIn('Exit Code: 143 (signal 15, SIGTERM)', result.stdout)

    def test_binary_output_is_preserved(self):
        """Non-UTF-8 output is forwarded byte for byte and does not crash the report."""
        payload = bytes(range(256))
        code = 'import sys; sys.stdout.buffer.write(bytes(range(256)))'
        result = self._run([sys.executable, '-c', code], text=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(result.stdout.startswith(payload))
        self.assertIn(b'Command:', result.stdout)
        self.assertNotIn(b'Traceback', result.stderr)

    def test_missing_command_exit_code(self):
        """A command that does not exist gives exit code 127 and no traceback."""
        result = self._run(['nonexistent_command_12345'])
        self.assertEqual(result.returncode, 127)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIn('nonexistent_command_12345', result.stderr)

    def test_exec_format_error_exit_code(self):
        """A file that cannot be exec'd (no shebang: ENOEXEC) gives 126 and no traceback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script = os.path.join(tmpdir, 'no-shebang')
            with open(script, 'w') as f:
                f.write('echo hi\n')
            os.chmod(script, 0o755)
            result = self._run([script])
            self.assertEqual(result.returncode, 126, msg=result.stderr)
            self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, msg=result.stderr)
            self.assertIn('no-shebang', result.stderr)

    def test_unwritable_out_file_keeps_exit_code(self):
        """If --out-file cannot be written, runit logs one line and keeps the command's exit code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, 'missing-dir', 'out.txt')
            for code in (0, 4):
                result = self._run(['--out-file', out_file, sys.executable, '-c',
                                    'raise SystemExit({})'.format(code)])
                self.assertEqual(result.returncode, code, msg=result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertEqual(len(result.stderr.strip().splitlines()), 1, msg=result.stderr)
                self.assertIn(out_file, result.stderr)
                self.assertIn('Exit Code: {}'.format(code), result.stdout)

    @unittest.skipIf(os.name != 'posix', 'POSIX pipes and the yes command')
    def test_closed_stdout_during_run_is_quiet(self):
        """`runit yes | head -1` ends quietly with the shell status of yes (141)."""
        proc = subprocess.Popen(['runit', '--log-level', 'WARNING', 'yes'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(proc.stdout.readline(), b'y\n')
            proc.stdout.close()  # like `head -1` exiting
            stderr = proc.communicate(timeout=self.TIMEOUT_SECONDS)[1].decode()
            self.assertEqual(proc.returncode, 128 + signal.SIGPIPE, msg=stderr)
            self.assertEqual(stderr, '')
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    @unittest.skipIf(os.name != 'posix', 'POSIX pipes')
    def test_closed_stdout_before_report_still_writes_out_file(self):
        """If stdout closes before the report, --out-file is still written and runit is quiet."""
        code = 'import time; print("one", flush=True); time.sleep(1)'
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, 'out.txt')
            proc = subprocess.Popen(['runit', '--log-level', 'WARNING', '--out-file', out_file,
                                     sys.executable, '-c', code],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.assertEqual(proc.stdout.readline(), b'one\n')
                proc.stdout.close()  # the reader goes away before the report
                stderr = proc.communicate(timeout=self.TIMEOUT_SECONDS)[1].decode()
                self.assertEqual(proc.returncode, 0, msg=stderr)
                self.assertEqual(stderr, '')
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            with open(out_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
            self.assertIn('Exit Code: 0', file_content)
            self.assertIn('one', file_content)

    @unittest.skipUnless(os.path.exists('/dev/full'), 'needs /dev/full')
    def test_full_stdout_gives_one_line_error(self):
        """A report that cannot be written (ENOSPC) gives one error line and the command's exit code."""
        with open('/dev/full', 'w') as full:
            result = subprocess.run(['runit', '--log-level', 'WARNING', sys.executable, '-c',
                                     'raise SystemExit(5)'],
                                    stdout=full, stderr=subprocess.PIPE, text=True,
                                    timeout=self.TIMEOUT_SECONDS)
        self.assertEqual(result.returncode, 5, msg=result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1, msg=result.stderr)

    def test_plot_has_no_plotting_error(self):
        """--plot draws charts with the supported plotext API."""
        result = self._run(['--plot', sys.executable, '-c', 'import time; time.sleep(1)'])
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn('Could not plot chart', result.stderr)
        self.assertIn('CPU % over time', result.stdout)



if __name__ == '__main__':
    unittest.main()
