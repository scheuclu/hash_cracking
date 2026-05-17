# Hash cracking

This is the code for my [investigation](https://www.scheuclu.com/posts/password_hash_crack) on password hash cracking.


## Requirements
- Working installation of [hashcat](https://hashcat.net/hashcat)
  - You can automatically install hashcat by running `bash setup.sh`
- Working installation of CUDA
- [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management


## Setup

```bash
uv sync
```

This will install Python 3.14 (pinned via `.python-version`) and the project dependencies into a local `.venv`.

To enable Gmail status emails, drop your OAuth `token.json` into the project root and update the `RECIPIENT`/`SENDER` constants in `mail_remote.py`.


## Usage

The hashes that I am looking for are stored in [hash_inputs.hash](./hash_inputs.hash).

Run hashcat through successively more compute-intensive configurations:

```bash
uv run hash-cracking
```

After each run, a status email is sent to my Gmail account so I am kept up to date with what hashes have been found.

Send a single test email:

```bash
uv run send-mail
```
