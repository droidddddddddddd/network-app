"""Compatibility entry point for the expanded authenticated companion smoke check."""
import argparse
import asyncio
from pathlib import Path
from extension2_browser_check import run, ROOT
if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--shots", type=Path, default=ROOT / "screenshots/extension")
    p.add_argument("--skip-real-x", action="store_true")
    args = p.parse_args(); asyncio.run(run(args.shots.resolve(), not args.skip_real_x))
