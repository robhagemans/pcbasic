PC-BASIC test suite
===================

From the repository root, use `python -m tests` to run tests.

Options:
- `--all` runs all tests (default if no other options given)
- `--unit` run unit tests only, skip BASIC tests
- `--fast` skip slow tests
- `--coverage` track coverage
- `--loud` show standard output
- `--reraise` re-raise unexpected exceptions to see traceback


Utilities for BASIC tests:
- `python -m tests.show <category>/<testname>` show output differences in failed test
- `python -m tests.make <category>/<testname>` create a new BASIC test
- `python -m tests.model <category>/<testname>` use DOSBox to (re)create the output model for a test
