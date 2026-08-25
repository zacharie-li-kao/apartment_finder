#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One watch cycle: scan every source, rebuild index.html, report what changed."""
import json, os, subprocess, sys, time
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
JST = timezone(timedelta(hours=9))
PY = sys.executable
ENV = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def snapshot():
    p = os.path.join(HERE, "db.json")
    if not os.path.exists(p):
        return {}
    return {k: (v.get("price"), v.get("gone", False))
            for k, v in json.load(open(p, encoding="utf-8")).items()}


LOCK = os.path.join(HERE, ".cycle.lock")
MAX_CYCLE_MIN = 45      # a healthy cycle is ~19 min


def _holder_alive():
    """A cycle killed mid-run (Ctrl-C, reboot, laptop lid) leaves its lock
    behind.  Waiting an hour to clear it would skip a scan for no reason."""
    try:
        pid = int(open(LOCK, encoding="utf-8").read().strip())
    except (ValueError, OSError):
        return False
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                         capture_output=True, text=True).stdout
    return str(pid) in out


def acquire():
    """Two schedulers now drive this (the Windows task and an in-session loop).
    Without a lock they can interleave writes to db.json and lose listings."""
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        age = (time.time() - os.path.getmtime(LOCK)) / 60
        # Stale if the holder is gone, or simply too old to be real: a cycle
        # runs ~19 min, and pid checks cannot be trusted (pids get reused, and
        # tasklist has reported dead pids as live).  The age ceiling is the
        # backstop that guarantees the loop always recovers on its own.
        if age > MAX_CYCLE_MIN or not _holder_alive():
            print(f"clearing stale lock ({age:.0f} min old)")
            os.unlink(LOCK)
            return acquire()
        print(f"another cycle has been running for {age:.0f} min — skipping")
        return False
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    return True


def main():
    if not acquire():
        return
    try:
        run()
    finally:
        try:
            os.unlink(LOCK)
        except OSError:
            pass


def run():
    before = snapshot()
    failed, incomplete = [], []
    for script in ("scan.py", "scan_gems.py", "build.py"):
        p = os.path.join(HERE, script)
        if not os.path.exists(p):
            continue
        r = subprocess.run([PY, "-u", p], cwd=HERE, env=ENV,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = (r.stdout or "") + (r.stderr or "")
        print(out, end="")
        # Always persist the scan transcript ourselves.  It used to be written
        # only by watch.bat's redirect, so a cycle started any other way lost
        # its throttling warnings.
        with open(os.path.join(HERE, "watch_run.log"), "a",
                  encoding="utf-8") as f:
            f.write(out)
        for ln in out.splitlines():
            if "INCOMPLETE" in ln:
                incomplete.append(ln.split()[0])
        if r.returncode:
            failed.append(script)

    db = json.load(open(os.path.join(HERE, "db.json"), encoding="utf-8"))
    new, moved, gone = [], [], []
    for k, v in db.items():
        if k not in before:
            if not v.get("gone") and v.get("verdict") != "reject":
                new.append(v)
        else:
            op, og = before[k]
            if op and v.get("price") and v["price"] != op:
                moved.append((v, op))
            if v.get("gone") and not og:
                gone.append(v)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    lines = [f"[{now} JST] {len(db)} tracked · "
             f"{sum(1 for v in db.values() if not v.get('gone'))} live · "
             f"+{len(new)} new · {len(moved)} price changes · {len(gone)} delisted"]
    for v in sorted(new, key=lambda x: -x.get("score", 0))[:15]:
        lines.append(f"  NEW  {v.get('score')} {v.get('ward')} {v.get('name','')[:26]} "
                     f"{v.get('price')}万 {v.get('area')}m² {v.get('floor')}F "
                     f"{v.get('direction') or '?'} — {v['url']}")
    for v, op in moved[:15]:
        lines.append(f"  PRICE {v.get('ward')} {v.get('name','')[:26]} "
                     f"{op}万 → {v.get('price')}万 — {v['url']}")
    for v in gone[:10]:
        lines.append(f"  GONE {v.get('ward')} {v.get('name','')[:26]}")

    report = "\n".join(lines)
    print(report)
    with open(os.path.join(HERE, "watch.log"), "a", encoding="utf-8") as f:
        f.write(report + "\n")


if __name__ == "__main__":
    main()
