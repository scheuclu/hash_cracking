# TODO — finish the portfolio sweep

After reboot, run the hashcat sweep on the GB10 (free of the long-running `gpt.py` job), then hand the results back so the README can be filled in.

## 1. Build hashcat (one-time)

No ARM64 prebuilt exists upstream, so we build 7.1.2 from source:

```bash
bash setup.sh
```

Needs sudo for `apt install build-essential curl`. Installs to `~/hashcat-7.1.2/`. Takes a few minutes.

## 2. Point the runner at the binary

```bash
export HASHCAT_BIN=$HOME/hashcat-7.1.2/hashcat
```

(Add to `~/.bashrc` if you want it permanent.)

## 3. Run the sweep

```bash
uv run hash-cracking
```

Walks 10 mask-attack configs against `hash_inputs.hash`. Output streams to the terminal and to `runs/{timestamp}_{desc}.log`. Each config appends a row to `results.csv`.

The long pole is `SHA1 len=8 symbol-flanked` (~95⁸ keyspace). Everything before it should finish in seconds-to-minutes. `Ctrl+C` is safe — completed rows persist in `results.csv`.

## 4. If re-running for a clean number

```bash
rm -rf runs/ results.csv
uv run hash-cracking
```

Fresh potfile means `newly_cracked` per config is accurate again.

## 5. Hand back

Paste `results.csv` into the chat (or just say "done" and Claude will read it). Then:

- Rewrite README around the GB10 + real timing numbers (task #11)
- One commit covers Phase A code changes + results + README

## Open decisions still pending

- Whether to include hashcat output screenshots / asciinema in the README.
- Whether to add a green-badge GitHub Actions workflow (just `uv sync` + import-check).
- LICENSE file (MIT, matching `pyproject.toml`).
