# Cracking SHA-1 on a Grace Blackwell GPU

A short hands-on investigation: how long does it really take to brute-force short, bare,
unsalted SHA-1 hashes on modern hardware?

> generated from [`results.csv`](./results.csv).

## What's in here

| File | What it does |
| --- | --- |
| [`run_combos.py`](./run_combos.py) | Drives hashcat through a staged sweep of mask attacks. Captures per-config timing and crack rate to `results.csv`, full output to `runs/`. |
| [`build_site.py`](./build_site.py) | Renders `results.csv` + project metadata into a self-contained `docs/index.html` (no JS, inline SVG chart). |
| [`setup.sh`](./setup.sh) | Builds hashcat 7.1.2 from source. Required on ARM64 / aarch64 systems since hashcat ships x86_64 binaries only. |
| [`hash_inputs.hash`](./hash_inputs.hash) | Three synthetic SHA-1 hashes (mode 100). Known plaintexts in `hash_inputs.solution` for self-verification. |
| [`results.csv`](./results.csv) | Per-mask timing and crack data from the sweep on an NVIDIA GB10. |

## Reproduce

Requires Linux, an NVIDIA GPU with CUDA drivers, and [`uv`](https://docs.astral.sh/uv/).

```bash
bash setup.sh                                      # builds hashcat 7.1.2 from source
export HASHCAT_BIN=$HOME/hashcat-7.1.2/hashcat
uv sync
uv run hash-cracking                               # populates results.csv + runs/
uv run python build_site.py                        # regenerates docs/index.html
```

`uv` pins Python 3.14 via [`.python-version`](./.python-version). The `hash-cracking` runner
honors `HASHCAT_BIN` (env) and falls back to `hashcat` on `PATH`.

## License

[MIT](./LICENSE).
