"""
Tests for bundler.py
"""
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv as pyvenv

import pytest

from bundler import _make_parser, bundle, repair, unpack


@pytest.fixture(name="parser")
def fixture_parser():
    yield _make_parser()


@pytest.fixture(name="venv")
def fixture_venv():
    venv_ = pyvenv.EnvBuilder(with_pip=True)
    tempdir = pathlib.Path(tempfile.mkdtemp("venv"))
    venv_.create(tempdir)

    yield tempdir

    shutil.rmtree(tempdir)


@pytest.fixture(name="venv_tgz")
def fixture_venv_tgz(venv):
    tgz = venv / "venv.tgz"
    with tarfile.open(tgz, "w:gz") as tar:
        for file in venv.glob("**/*"):
            tar.add(file, arcname=file.relative_to(venv))
    yield tgz
    tgz.unlink()


def test_parser(parser):
    parser.parse_args(["bundle"])

    with tempfile.NamedTemporaryFile() as tmpfile:
        assert parser.parse_args(["unpack", tmpfile.name]).do_repair is True
        assert (
            parser.parse_args(["unpack", "--no-repair", tmpfile.name]).do_repair is False
        )
        assert (
            parser.parse_args(
                ["unpack", "--shebang", "/usr/bin/python3.10", tmpfile.name]
            ).shebang
            == "/usr/bin/python3.10"
        )
        assert parser.parse_args(
            ["unpack", "--python", sys.executable, tmpfile.name]
        ).python == pathlib.Path(sys.executable)

    with tempfile.TemporaryDirectory() as tmpdir:
        parser.parse_args(["repair", tmpdir])
        parser.parse_args(["repair", "--shebang", "/usr/bin/python3.10", tmpdir])
        parser.parse_args(["repair", "--python", sys.executable, tmpdir])


def test_bundle(venv):
    output = venv.with_suffix(".tgz")
    try:
        bundle(venv, output=output)

        assert output.is_file()
        assert output.stat().st_size > 0

        with tarfile.open(output, "r:*") as tar:
            assert "bin" in tar.getnames()
            assert "bin/python" in tar.getnames()

    finally:
        output.unlink()


def test_unpack(venv_tgz):
    output = venv_tgz.with_suffix("")
    try:
        unpack(venv_tgz, output)

        assert output.is_dir()
        assert (output / "bin" / "python").is_file()

    finally:
        shutil.rmtree(output)


def test_repair(venv: pathlib.Path):
    bin_false = pathlib.Path(shutil.which("false")).resolve()
    bin_executable = pathlib.Path(sys.executable)
    venv_python = venv / "bin" / "python"
    venv_pip = venv / "bin" / "pip"

    # First we just test we repair (break) the venv correctly
    repair(venv, shebang=pathlib.Path("/does/not/exists/python3.10"), python=bin_false)

    assert venv_python.is_symlink()
    assert venv_python.resolve() == bin_false

    assert venv_pip.is_file()
    with venv_pip.open("r") as fp_pip:
        assert fp_pip.readline() == "#!/does/not/exists/python3.10\n"

    repair(venv, shebang=venv_python, python=bin_executable)
    assert venv_python.is_symlink()
    assert venv_python.readlink() == bin_executable

    assert venv_pip.is_file()
    with venv_pip.open("r") as fp_pip:
        assert fp_pip.readline() == f"#!{venv_python}\n"

    subprocess.run([venv_pip, "--version"], check=True)


if __name__ == "__main__":
    pytest.main()
