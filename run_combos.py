"""Drive hashcat through successively more compute-intensive configurations."""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

import mail_remote as mail

HASHCAT_BIN = Path.home() / "hashcat-6.2.5" / "hashcat.bin"
POTFILE = Path("../hashcat-6.2.5/hashcat.potfile")
DEFAULT_HASHFILE = Path("./hash_inputs.hash")


@dataclass(frozen=True, slots=True)
class Config:
    desc: str
    hashfile: Path
    potfile: Path
    hashcat_mode: str
    hashcat_pattern: str

    def command(self) -> list[str]:
        return [
            str(HASHCAT_BIN),
            *shlex.split(self.hashcat_mode),
            str(self.hashfile),
            *shlex.split(self.hashcat_pattern),
        ]


def gen_all_configs(name: str, hashfile: Path, hashcode: int) -> list[Config]:
    hashfile = hashfile.resolve(strict=True)
    return [
        *(
            Config(
                desc=f"{name}: {length} lowercase and numbers",
                hashfile=hashfile,
                potfile=POTFILE,
                hashcat_mode=f"-m {hashcode} -a 3",
                hashcat_pattern=f"-1 ?l?d {'?1' * length}",
            )
            for length in (6, 7, 8, 9)
        ),
        *(
            Config(
                desc=f"{name}: {length} FRONTupper_MIDlowernum_ENDlowernum",
                hashfile=hashfile,
                potfile=POTFILE,
                hashcat_mode=f"-m {hashcode} -a 3",
                hashcat_pattern=f"-1 ?l?d -2 ?u ?2{'?1' * (length - 1)}",
            )
            for length in (6, 7, 8)
        ),
        *(
            Config(
                desc=f"{name}: {length} FRONTuppersymbol_MIDlowernum_ENDuppersymbolnum",
                hashfile=hashfile,
                potfile=POTFILE,
                hashcat_mode=f"-m {hashcode} -a 3",
                hashcat_pattern=f"-1 ?u?l?s -2 ?l?d -3 ?u?s?d ?1{'?2' * (length - 2)}?3",
            )
            for length in (6, 7, 8)
        ),
    ]


def run_config(config: Config) -> None:
    mail.send_string_via_mail(f"Starting {config.desc}")
    cmd = config.command()
    print(shlex.join(cmd))
    subprocess.run(cmd, check=False)
    if config.potfile.exists():
        mail.send_file_via_mail(config.potfile)
    print("done")


def main() -> None:
    configs = gen_all_configs("SHA1", DEFAULT_HASHFILE, hashcode=110)
    for config in configs:
        run_config(config)


if __name__ == "__main__":
    main()
