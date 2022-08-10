from dataclasses import dataclass
import os
import mail_remote as mail

class FilePath:
    def __init__(self, path):
        if not os.path.exists(path):
            raise Exception(f"Filepath does not exist: {path}")
        self.path=path
    def __repr__(self):
        return f"FilePath<{self.path}>"

    def __str__(self):
        return self.path

@dataclass
class Config:
    desc: str
    hashfile: FilePath
    potfile: FilePath
    hashcat_mode: str
    hashcat_pattern: str


def gen_all_configs(name: str, hashfile: str, hashcode: int):
    return [
    *[Config(
      desc=f"{name}: {l} lowercase and numbers",
      hashfile=FilePath(hashfile),
      potfile=FilePath("../hashcat-6.2.5/hashcat.potfile"),
      hashcat_mode=f"-m {hashcode} -a 3",
      hashcat_pattern=f"-1 ?l?d {'?1'*l}") for l in [6, 7, 8, 9] ],
    *[Config(
        desc=f"{name}: {l} FRONTupper_MIDlowernum_ENDlowernum",
        hashfile=FilePath(hashfile),
        potfile=FilePath("../hashcat-6.2.5/hashcat.potfile"),
        hashcat_mode=f"-m {hashcode} -a 3",
        hashcat_pattern=f"-1 ?l?d -2 ?u ?2{'?1' * (l-1)}") for l in [6, 7, 8]],
    *[Config(
        desc=f"{name}: {l} FRONTuppersymbol_MIDlowernum_ENDuppersymbolnum",
        hashfile=FilePath(hashfile),
        potfile=FilePath("../hashcat-6.2.5/hashcat.potfile"),
        hashcat_mode=f"-m {hashcode} -a 3",
        hashcat_pattern=f"-1 ?u?l?s -2 ?l?d -3 ?u?s?d  ?1{'?2' * (l - 2)}?3") for l in [6, 7, 8]]
    ]


configs_sha1salt_K = gen_all_configs("SHA1", "./hash_inputs.hash", 110)


for c in [*configs_sha1salt_K]:
    mail.send_string_via_mail(f"Starting {c.desc}")
    command=f"~/hashcat-6.2.5/hashcat.bin {c.hashcat_mode} {c.hashfile} {c.hashcat_pattern}"
    print(command)
    os.system(command)
    mail.send_file_via_mail(c.potfile.path)
    print("done")

