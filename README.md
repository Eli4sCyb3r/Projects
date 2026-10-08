# Projects

A small collection of Bash automation scripts for running anonymized remote
reconnaissance (WHOIS + Nmap) against a user-specified target, driven from a
local machine over SSH.

## Repository layout

```
.
├── README.md                  # You are here
└── scripts/
    ├── installations.sh       # Remote host setup (dependencies + anonymization)
    └── project.nr.sh          # Orchestrator: connect, verify anonymity, scan, collect results
```

## Scripts

### `scripts/installations.sh`
Prepares the **remote** host:
- Installs the required packages if they are not already present.
- Installs and activates the anonymization layer so the remote host routes
  traffic anonymously.

### `scripts/project.nr.sh`
The main entry point. It:
1. Prompts for the remote host's IP, username, and password.
2. Ensures both the local and remote hosts are anonymous before continuing,
   and exits if either is not.
3. Copies `installations.sh` to the remote host and runs it.
4. Displays remote host details (IP, country, uptime).
5. Runs the requested WHOIS and Nmap scans from the remote host.
6. Copies the results back to the local machine and cleans up the remote side.
7. Logs each step to a local log file for auditing.

## Usage

```bash
bash scripts/project.nr.sh
```

You will be prompted for the remote host connection details and the address to
scan. Results are saved to the local Desktop and actions are recorded in the
log file.

> **Note:** These scripts are intended for authorized testing only. Run them
> solely against hosts and targets you own or have explicit permission to test.
