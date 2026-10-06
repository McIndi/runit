# Changes

## Unreleased (0.1.5)

- Fixed: `--out-file` no longer crashes the output thread or kills the command with a broken pipe. All output of the command is shown and captured.
- Fixed: output larger than the pipe buffer (about 64 KB) no longer makes runit hang. This was fixed on main by streaming stdout and stderr (PR #1). The 0.1.4 release still has the hang.
- Changed: runit exits with the exit code of the command (128 + N for signal N, 127 when the command is not found, 126 when it cannot be executed). Before, it exited with 0. The report shows `Exit Code`.
- Changed: the plotext dependency is pinned to `plotext>=5.3,<6`. plotext 6 replaced the API that `--plot` uses, so charts were silently skipped, and plotext 5.2 draws empty charts. runit now logs a clear warning if an unsupported plotext is installed.
- Tests: added regression tests that run the installed `runit` command for these cases.
