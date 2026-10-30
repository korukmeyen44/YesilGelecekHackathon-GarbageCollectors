"""Compile production C++ core on the host and run Python/HTTP integration tests."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default=os.environ.get("CXX", "g++"))
    args = parser.parse_args()
    compiler = shutil.which(args.cxx)
    if not compiler:
        parser.error("C++ compiler not found; install g++ or specify --cxx")
    build = ROOT / ".build"
    build.mkdir(exist_ok=True)
    executable = build / ("test_core.exe" if os.name == "nt" else "test_core")
    fixture = build / "gateway_fixture.json"
    link_flags = ["-static"] if os.name == "nt" else []
    subprocess.run([compiler, "-std=c++11", "-Wall", "-Wextra", "-Werror", "-pedantic", *link_flags,
                    "-I", str(ROOT / "include"), str(ROOT / "tests/native/test_core.cpp"),
                    "-o", str(executable)], check=True)
    subprocess.run([str(executable), str(fixture)], check=True)
    env = dict(os.environ, GC_CPP_JSON_FIXTURE=str(fixture), PYTHONDONTWRITEBYTECODE="1")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests/python"),
                    "-v"], cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()

