#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One watch cycle: scan every source, rebuild index.html, report what changed."""
import json, os, subprocess, sys
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


def main():
    before = snapshot()
    failed = []
    for script in ("scan.py", "scan_gems.py"):
        p = os.path.join(HERE, script)
        if not os.path.exists(p):
            continue
        if subprocess.run([PY, "-u", p], cwd=HERE, env=ENV).returncode:
            failed.append(script)
    if subprocess.run([PY, "-u", os.path.join(HERE, "build.py")],
                      cwd=HERE, env=ENV).returncode:
        failed.append("build.py")

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
