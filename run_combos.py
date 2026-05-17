"""Drive hashcat through staged mask attacks and capture timing + crack rate."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_HASHFILE = PROJECT_ROOT / "hash_inputs.hash"
RUNS_DIR = PROJECT_ROOT / "runs"
POTFILE = RUNS_DIR / "hashcat.potfile"
RESULTS_CSV = PROJECT_ROOT / "results.csv"


@dataclass(frozen=True, slots=True)
class Config:
    desc: str
    hashcat_mode: str
    hashcat_pattern: str


def gen_all_configs(name: str, hashcode: int) -> list[Config]:
    configs: list[Config] = []
    for length in (6, 7, 8, 9):
        configs.append(
            Config(
                desc=f"{name} len={length} lowercase+digits",
                hashcat_mode=f"-m {hashcode} -a 3",
                hashcat_pattern=f"-1 ?l?d {'?1' * length}",
            )
        )
    for length in (6, 7, 8):
        configs.append(
            Config(
                desc=f"{name} len={length} upper+lowerdigit",
                hashcat_mode=f"-m {hashcode} -a 3",
                hashcat_pattern=f"-1 ?l?d -2 ?u ?2{'?1' * (length - 1)}",
            )
        )
    for length in (6, 7, 8):
        configs.append(
            Config(
                desc=f"{name} len={length} symbol-flanked",
                hashcat_mode=f"-m {hashcode} -a 3",
                hashcat_pattern=f"-1 ?u?l?s -2 ?l?d -3 ?u?s?d ?1{'?2' * (length - 2)}?3",
            )
        )
    return configs


def find_hashcat_bin() -> Path:
    explicit = os.environ.get("HASHCAT_BIN")
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"HASHCAT_BIN points to missing file: {path}")
        return path
    on_path = shutil.which("hashcat")
    if on_path:
        return Path(on_path)
    raise FileNotFoundError(
        "hashcat not found. Install it or set HASHCAT_BIN to the hashcat binary path."
    )


def potfile_line_count(potfile: Path) -> int:
    if not potfile.exists():
        return 0
    with potfile.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


RECOVERED_RE = re.compile(r"Recovered\.+:\s*(\d+)/(\d+)")


def parse_recovered(text: str) -> tuple[int, int] | None:
    for line in reversed(text.splitlines()):
        m = RECOVERED_RE.search(line)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def _slugify(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def run_config(
    config: Config,
    *,
    hashcat_bin: Path,
    hashfile: Path,
    potfile: Path,
    runs_dir: Path,
) -> dict[str, object]:
    started_at = datetime.now(timezone.utc)
    cracked_before = potfile_line_count(potfile)

    cmd: list[str] = [
        str(hashcat_bin),
        *shlex.split(config.hashcat_mode),
        f"--potfile-path={potfile}",
        "--status",
        "--status-timer=10",
        str(hashfile),
        *shlex.split(config.hashcat_pattern),
    ]
    print(f"$ {shlex.join(cmd)}", flush=True)

    log_path = runs_dir / f"{started_at.strftime('%Y%m%dT%H%M%SZ')}_{_slugify(config.desc)}.log"

    t0 = time.perf_counter()
    captured: list[str] = []
    with log_path.open("w", encoding="utf-8") as logf:
        logf.write(f"$ {shlex.join(cmd)}\n\n")
        logf.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            logf.write(line)
            captured.append(line)
        exit_code = proc.wait()
    duration = time.perf_counter() - t0

    cracked_after = potfile_line_count(potfile)
    recovered = parse_recovered("".join(captured))
    total = recovered[1] if recovered else 0
    newly = max(0, cracked_after - cracked_before)
    print(
        f"  -> {duration:.2f}s  newly={newly}  cumulative={cracked_after}/{total}  exit={exit_code}",
        flush=True,
    )
    return {
        "timestamp": started_at.isoformat(timespec="seconds"),
        "desc": config.desc,
        "hashcat_args": f"{config.hashcat_mode} {config.hashcat_pattern}",
        "duration_seconds": round(duration, 3),
        "newly_cracked": newly,
        "cumulative_cracked": cracked_after,
        "total_hashes": total,
        "exit_code": exit_code,
        "log": log_path.name,
    }


CSV_FIELDS = [
    "timestamp",
    "desc",
    "hashcat_args",
    "duration_seconds",
    "newly_cracked",
    "cumulative_cracked",
    "total_hashes",
    "exit_code",
    "log",
]


def append_result(row: dict[str, object], path: Path) -> None:
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hashfile", type=Path, default=DEFAULT_HASHFILE)
    parser.add_argument("--name", default="SHA1")
    parser.add_argument(
        "--mode",
        type=int,
        default=100,
        help="hashcat -m mode code (100 = bare SHA-1)",
    )
    args = parser.parse_args()

    hashcat_bin = find_hashcat_bin()
    hashfile = args.hashfile.resolve(strict=True)
    RUNS_DIR.mkdir(exist_ok=True)

    print(f"hashcat:  {hashcat_bin}")
    print(f"hashfile: {hashfile}")
    print(f"potfile:  {POTFILE}")
    print(f"runs dir: {RUNS_DIR}")
    print(f"results:  {RESULTS_CSV}")
    print()

    for config in gen_all_configs(args.name, args.mode):
        print(f"=== {config.desc} ===")
        row = run_config(
            config,
            hashcat_bin=hashcat_bin,
            hashfile=hashfile,
            potfile=POTFILE,
            runs_dir=RUNS_DIR,
        )
        append_result(row, RESULTS_CSV)


if __name__ == "__main__":
    main()
