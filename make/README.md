PC-BASIC packaging toolset
==========================

From the repository root:

- `python -m make` creates a package for your system (Linux, Windows or macOS only).
- `python -m make local` sets up what is needed to run locally from the repository.
- `python -m make build` creates a wheel and an sdist package.
- `python -m make docs` builds the documentation.
- `python -m make ready` prepares documentation and resources for a build.
- `python -m make clean` removes intermediate packaging files.
