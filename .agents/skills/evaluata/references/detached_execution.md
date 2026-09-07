# Windows Detached Execution Guide (SSH-Resilient Runner)

> **Context**: Detached execution architecture on Windows host machines, referenced by [`evaluata`](../SKILL.md) and [`improva`](../improva/SKILL.md).

---

## The Problem: SSH Drop Child Process Termination

When running long-running backtests, A/B sweeps, multi-week Monte Carlo simulations, or baseline generation (`generate_baseline_archive.py`), **never run scripts in an interactive foreground shell attached to an SSH session**. If the SSH connection drops, Windows terminates all child processes attached to that terminal session, corrupting or aborting hours of execution.

---

## The Detached Execution Standard

All long-running jobs MUST be launched as independent background processes detached from the shell session, redirecting `stdout` and `stderr` to persistent log files:

### 1. Batch Runner Script (`scratch/run_<job>.bat`)
```cmd
@echo off
cd /d "F:\Google Drive\Documents\Hobbies\Lacrosse\PLL fantasy\scripts"
python -u "scratch\<script>.py" > "scratch\<job>.log" 2>&1
```

### 2. Silent Detached VBS Launcher (`scratch/start_<job>_silent.vbs`)
```vbs
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c ""F:\Google Drive\Documents\Hobbies\Lacrosse\PLL fantasy\scripts\scratch\run_<job>.bat""", 0, False
```
*The second argument `0` hides the window completely; the third argument `False` returns immediately without blocking.*

### 3. Execution Command
Launch the runner via:
```bash
wscript scratch/start_<job>_silent.vbs
```
or
```bash
cscript //nologo scratch/start_<job>_silent.vbs
```

### 4. Monitoring Progress
Inspect the log asynchronously without attaching:
```powershell
Get-Content -Path "scratch\<job>.log" -Tail 30 -Wait
```
