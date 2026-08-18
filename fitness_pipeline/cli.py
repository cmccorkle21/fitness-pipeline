from __future__ import annotations
import argparse
from .db import connect, migrate
from .mappings import seed_mappings
from .sync import sync

def main():
    parser=argparse.ArgumentParser(description="Sync Hevy workouts into local SQLite.")
    parser.add_argument("--full", action="store_true", help="Fetch and reconcile every workout now.")
    parser.add_argument("--seed-mappings", action="store_true", help="Seed empty mappings from retired title rules.")
    args=parser.parse_args()
    mode,count=sync(force_full=args.full)
    if args.seed_mappings:
        seeded=seed_mappings(connect()); print(f"{mode} sync complete: {count} changed; seeded {seeded} mappings")
    else: print(f"{mode} sync complete: {count} changed")
if __name__ == "__main__": main()
