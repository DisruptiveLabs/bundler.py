bundler.py
==========

A simple tool for packing shippable virtualenvs

### bundler.py bundle [-h] [--output OUTPUT] [--compression {gz,bz2,xz} | --gz | --bz2 | --xz] [venv]

Bundle a virtualenv folder into a tarball, ready for caching or shipping between environments

Output files are just compressed tar files, with an additional metadata file (currently unused, but 
intended for future validation post-unpacking)

### bundler.py unpack [-h] [--shebang SHEBANG] [--python PYTHON] [--no-repair] bundle_path [output]

Unpack and optionally repair a bundle into a usable virtualenv

### bundler.py repair [-h] [--shebang SHEBANG] [--python PYTHON] path

Repair a virtualenv, rewriting `venv/bin` script shebangs, and updating `bin/python` symlinks to point
to the correct path.

Future versions will inspect shebangs before rewriting, so as not to break potential shell scripts
and other files that get stuck in `venv/bin`

## Development

This project uses poetry for development dependency management, although it's not strictly necessary.

`py.test` is used for testing, `flakeheaven` for linting, and `black` for formatting.
