#!/usr/bin/env python3
"""
Virtualenv bundler and repair tool.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import os
import pathlib
import re
import sys
import tarfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal

logger = logging.getLogger()


def _get_venv() -> pathlib.Path:
    if virtual_env := os.environ.get("VIRTUAL_ENV", None):
        return pathlib.Path(virtual_env)
    return pathlib.Path(sys.exec_prefix)


def bundle(
    venv: pathlib.Path,
    output: pathlib.Path | None = None,
    compression: None | Literal["gz", "bz2", "xz"] = None,
):
    """
    Bundle a virtualenv into a tarball.
    """
    if not output:
        output = pathlib.Path(".") / venv.with_suffix(".tar.gz").name
    if not compression:
        if groups := re.match(r"(gz|bz2|xz)$", output.suffix):
            compression = groups[0]

    logger.info("Bundling virtualenv to %s", output)
    try:
        mode = "w"
        if compression:
            mode += ":" + compression

        with tarfile.open(output, mode) as tar:
            metadata = json.dumps(
                {
                    "version": "1",
                    "path": venv.as_posix(),
                    "prefix": (venv / "bin" / "python").resolve().as_posix(),
                }
            ).encode("UTF-8")
            buf = io.BytesIO(metadata)
            tarinfo = tarfile.TarInfo(".__bundler.json")
            tarinfo.size = len(metadata)
            tar.addfile(tarinfo, buf)

            for file in venv.glob("**/*"):
                logger.debug("Adding %s", file.relative_to(venv))

                tar.add(file, arcname=str(file.relative_to(venv)))

    except (KeyboardInterrupt, Exception):
        output.unlink()
        raise


def unpack(
    bundle_path: pathlib.Path,
    output: pathlib.Path,
    do_repair=False,
    **repair_kwargs,
):
    """
    Unpack a virtualenv from a tarball.
    """
    with tarfile.open(bundle_path) as tar:
        tar.extractall(output)

    if do_repair:
        repair(output, **repair_kwargs)


def repair(venv: pathlib.Path, shebang=None, python=None):
    """
    Repair a virtualenv.
    """
    if python:
        for bin_python in venv.glob("bin/python*"):
            bin_python.unlink()
            bin_python.symlink_to(python)

    if not shebang:
        shebang = (venv / "bin" / "python").absolute()

    for bin_file in venv.glob("bin/*"):
        if bin_file.is_file() and not bin_file.is_symlink():
            try:
                first_line, *lines = bin_file.read_text().splitlines()
                if first_line.startswith("#!"):
                    logger.debug('Repairing "%s"', bin_file)
                    with bin_file.open("w") as file:
                        file.write(f"#!{shebang}\n")
                        file.write("\n".join(lines))
            except UnicodeDecodeError:
                continue


def _make_parser():
    @contextlib.contextmanager
    def _(val):
        yield val

    def _path_file(val) -> pathlib.Path:
        path = pathlib.Path(val)
        if not path.resolve().is_file():
            raise argparse.ArgumentTypeError(f"{val} is not a file")
        return path

    def _path_dir(val) -> pathlib.Path:
        path = pathlib.Path(val)
        if not path.resolve().is_dir():
            raise argparse.ArgumentTypeError(f"{val} is not a directory")
        return path

    def _path_output(val) -> pathlib.Path:
        path = pathlib.Path(val)
        if path.resolve().exists():
            raise argparse.ArgumentTypeError(f"{val} already exists")
        return path

    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")

    subparsers = parser.add_subparsers(required=True)

    with _(
        subparsers.add_parser(
            "bundle",
            help="Bundle a virtualenv into a tarball.",
            aliases=["b"],
        )
    ) as parse_bundle:
        parse_bundle.set_defaults(func=bundle)
        parse_bundle.add_argument(
            "--output",
            "-o",
            type=_path_output,
            help="Path to the output tarball.",
        )
        parse_bundle.add_argument(
            "venv",
            nargs="?",
            default=_get_venv(),
            type=_path_dir,
            help=f"Path to the virtualenv to bundle. Default: {sys.exec_prefix}",
        )

        with _(parse_bundle.add_mutually_exclusive_group()) as compression_group:
            compression_group.add_argument(
                "--compression",
                "-c",
                choices=["gz", "bz2", "xz"],
                help="Compression type.",
            )
            compression_group.add_argument(
                "--gz",
                "-z",
                action="store_const",
                const="gz",
                dest="compression",
                help="Compress with gzip.",
            )
            compression_group.add_argument(
                "--bz2",
                "-b",
                action="store_const",
                const="bz2",
                dest="compression",
                help="Compress with bzip2.",
            )
            compression_group.add_argument(
                "--xz",
                "-x",
                action="store_const",
                const="xz",
                dest="compression",
                help="Compress with xz.",
            )

    with _(argparse.ArgumentParser(add_help=False)) as repair_arguments:
        repair_arguments.add_argument(
            "--shebang",
            "-s",
            help="Shebang to inject into all scripts in venv/bin",
        )
        repair_arguments.add_argument(
            "--python",
            "-p",
            type=_path_file,
            help="Path to the Python interpreter to use.\n"
            "Repairs the venv/bin/python symlink",
        )

        with _(
            subparsers.add_parser(
                "unpack",
                help="Unpack a virtualenv from a tarball.",
                aliases=["u"],
                parents=[repair_arguments],
            )
        ) as parse_unpack:
            parse_unpack.set_defaults(func=unpack)
            parse_unpack.add_argument(
                "bundle_path",
                type=_path_file,
                help="Path to the tarball to unpack.",
            )
            parse_unpack.add_argument(
                "output",
                nargs="?",
                default=pathlib.Path("./venv"),
                type=_path_output,
                help="Path to the output virtualenv.",
            )
            parse_unpack.add_argument(
                "--no-repair",
                dest="do_repair",
                action="store_false",
                default=True,
                help="Don't repair the virtualenv after unpacking.",
            )

        with _(
            subparsers.add_parser(
                "repair",
                help="Repair a virtualenv.",
                aliases=["r"],
                parents=[repair_arguments],
            )
        ) as parse_repair:
            parse_repair.set_defaults(func=repair)
            parse_repair.add_argument(
                "venv",
                type=_path_dir,
                help="Path to the virtualenv to repair.",
            )

    return parser


def main():
    argument_parser = _make_parser()
    args = argument_parser.parse_args().__dict__

    func = args.pop("func")

    logging.basicConfig(
        level=logging.DEBUG if args.pop("verbose", False) else logging.INFO
    )
    logger.debug("Running %s with args %r", func.__name__, args)
    func(**args)


if __name__ == "__main__":
    main()
