"""
Every relation a reference record declares names a record this realm also ships.

The appliance's seed refuses a record WHOLE when one of its relations names nothing — so one misprinted chapter in
an Article's proofs (`PROVED_BY` Ecclesiastes 17, where Ecclesiastes has twelve) cost the realm that Article, and
the appliance warned only "3 record(s) still failing" on every load. This check finds such a record before it ships:

    python3 tests/reference_targets.py

Offline and quick (a few seconds); no appliance needed. A target of a type another realm ships (none today) would
be reported here too, and belongs in ALLOWED_ELSEWHERE once it is meant. Exits non-zero, naming each record, when any
target is missing.
"""
import collections
import glob
import os
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
# Target types this realm relies on another realm to ship: none.
ALLOWED_ELSEWHERE = set()


def load(pattern):
    for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
        with open(path) as f:
            yield os.path.basename(path), yaml.load(f, Loader=LOADER) or []


def ancestors():
    """Each declared type's own name and its parents', transitively — a record of a child answers for its parent."""
    parents = {t["name"]: t.get("parents") or [] for _, types in load("types/*.yml") for t in types if "name" in t}

    def up(name, seen=()):
        return {name}.union(*(up(p, seen + (name,)) for p in parents.get(name, []) if p not in seen))
    return up


def main():
    up = ancestors()
    records = [(f, r) for f, rs in load("reference/*.yml") for r in rs]
    held = collections.defaultdict(list)
    for _, r in records:
        for t in up(r["type"]):
            held[t].append(r["data"])
    index, missing = {}, []
    for f, r in records:
        for rel in r.get("relations") or []:
            to = dict(rel["to"])
            target = to.pop("type")
            if target in ALLOWED_ELSEWHERE:
                continue
            keys = tuple(sorted(to))
            known = index.setdefault((target, keys), {tuple(str(d.get(k)) for k in keys) for d in held[target]})
            if tuple(str(to[k]) for k in keys) not in known:
                name = r["data"].get("key") or r["data"].get("osis") or r["data"].get("name")
                missing.append(f"{f}: {r['type']} {name} -{rel['predicate']}-> {target} {to}")
    for line in missing:
        print("MISSING", line)
    print(f"{len(records)} records checked; {len(missing)} relation target(s) missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
