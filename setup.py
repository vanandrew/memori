from pathlib import Path
from setuptools import setup

# get the current dir
THISDIR = Path(__file__).parent

# get scripts path
scripts_path = THISDIR / "memori" / "scripts"

setup(
    entry_points={
        "console_scripts": [
            f"{f.stem}=memori.scripts.{f.stem}:main" for f in scripts_path.glob("*.py") if f.name not in "__init__.py"
        ]
    },
)
