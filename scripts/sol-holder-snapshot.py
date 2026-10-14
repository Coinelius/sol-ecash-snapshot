#!/usr/bin/env python3
"""Snapshot the holders of the pump.fun $eCash token on Solana.

Run this the moment the beta fork block is mined. It captures every holder,
anchors the result to a Solana slot and the beta fork block hash, prints a
SHA-256 digest, and optionally OpenTimestamps the file.

How the timestamp works
-----------------------
Two bounds pin *when the file existed*:

* **Not-before** — the beta fork block hash is unpredictable until that block
  is mined, and it is embedded in the JSON. The file cannot predate the fork.
* **Not-after** — the SHA-256 is committed somewhere immutable. `--stamp`
  submits it to the OpenTimestamps calendars, which batch it into a Bitcoin
  transaction *they* pay for; no coins and no transaction needed on your side.
  Run `ots upgrade` an hour or so later to turn the pending receipt into a
  Bitcoin-anchored proof.

That proves the list was not altered afterwards. It does NOT prove the list
faithfully reflects chain state — `getProgramAccounts` has no historical mode,
so nobody can re-query this slot later to check. Publish the raw file promptly
so others can compare against their own concurrent snapshot.

Why the query is built this way
-------------------------------
* The mint is **Token-2022** (`TokenzQd...`), not the classic SPL Token
  program. Filtering against `Tokenkeg...` silently returns zero accounts.
* Token-2022 accounts are **not** a fixed 165 bytes — extensions resize them —
  so the usual `dataSize: 165` filter silently drops holders. Filter on the
  mint alone.
* `dataSlice` returns only owner (32 bytes) + amount (u64 LE) per account,
  keeping the response small where `jsonParsed` would be enormous.
* `getTokenLargestAccounts` is not used: the public RPC rate-limits it hard and
  it returns 20 *token accounts*, un-deduped, not owners.
* One owner can hold through several token accounts, so balances are summed
  per owner before ranking.
* **Program-owned accounts are excluded.** The PumpSwap pool holds ~10% of
  supply and is not a holder; leaving it in displaces a real wallet from the
  top 15 and silently changes a rank-weighted payout. Exclusions are recorded
  with their balance and rank so every one of them is auditable.

No API key and no third-party indexer: this runs against the free public RPC.

Usage
-----
    python3 sol-holder-snapshot.py --fork-hash <beta block hash> [--stamp]

Get the fork block hash from the beta node once it has the block:

    bitcoin-cli -datadir=/opt/beta-data -conf=/opt/beta-data/beta.conf \
        -rpcport=8632 getblockhash 967680
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request

RPC = "https://api.mainnet-beta.solana.com"
MINT = "cTxqg4vt21u1Q2f9DSEig6S1fxmxLSsUV2v2wWspump"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SYSTEM_PROGRAM = "11111111111111111111111111111111"
DECIMALS = 6
FORK_HEIGHT = 967680
# The module's own path, not node_modules/.bin/ots-cli.js: npm drops that
# symlink when any other package claiming the same bin name is uninstalled,
# leaving a dangling link. The file below is the package itself.
OTS_BIN = os.path.expanduser("~/.local/ots/node_modules/opentimestamps/ots-cli.js")

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw: bytes) -> str:
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = B58[rem] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\x00"))) + out


def rpc(method, params, retries=5):
    """Call the public RPC, retrying on the 429s it hands out freely."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(RPC, body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read())
        except Exception as exc:                      # network hiccup, not a protocol error
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}: {exc}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
            continue
        if "error" in payload:
            if attempt == retries - 1:
                raise RuntimeError(payload["error"])
            print(f"  retry {attempt + 1}: {payload['error'].get('message')}", file=sys.stderr)
            time.sleep(3 * (attempt + 1))
            continue
        return payload["result"]
    raise RuntimeError("unreachable")


def fetch_balances():
    """Every token account for the mint, summed per owner. Returns (slot, totals, count)."""
    result = rpc("getProgramAccounts", [
        TOKEN_2022,
        {
            "encoding": "base64",
            "withContext": True,
            "dataSlice": {"offset": 32, "length": 40},   # owner(32) + amount(8)
            "filters": [{"memcmp": {"offset": 0, "bytes": MINT}}],
        },
    ])
    slot = result["context"]["slot"]
    totals, accounts = {}, result["value"]
    for acct in accounts:
        raw = base64.b64decode(acct["account"]["data"][0])
        owner = b58encode(raw[0:32])
        totals[owner] = totals.get(owner, 0) + int.from_bytes(raw[32:40], "little")
    return slot, totals, len(accounts)


def classify(owners):
    """Split owners into real wallets and program-owned accounts (pools, escrows)."""
    programs = {}
    for i in range(0, len(owners), 100):              # getMultipleAccounts caps at 100
        batch = owners[i:i + 100]
        values = rpc("getMultipleAccounts", [batch, {"encoding": "base64",
                                                     "dataSlice": {"offset": 0, "length": 0}}])["value"]
        for addr, info in zip(batch, values):
            if info is not None and info["owner"] != SYSTEM_PROGRAM:
                programs[addr] = info["owner"]        # a closed account is still a wallet
    return programs


def stamp(path, ots_bin):
    """Submit the file's hash to the OpenTimestamps calendars. No coins required."""
    if not os.path.exists(ots_bin):
        print(f"\nots client not found at {ots_bin} — skipping stamp.", file=sys.stderr)
        print("install: npm install --prefix ~/.local/ots opentimestamps", file=sys.stderr)
        return False
    print("\nstamping with OpenTimestamps ...")
    proc = subprocess.run(["node", ots_bin, "stamp", path],
                          capture_output=True, text=True, timeout=180)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0 or not os.path.exists(path + ".ots"):
        print("stamp FAILED — commit the digest another way before publishing.", file=sys.stderr)
        return False
    print(f"wrote {path}.ots  (keep it beside the .json)")
    print("in ~1h, anchor it in Bitcoin:")
    print(f"  node {ots_bin} upgrade {path}.ots")
    print(f"  node {ots_bin} verify  {path}.ots")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fork-hash", required=True,
                    help="beta block hash at height 967680 — proves the snapshot came after the fork")
    ap.add_argument("--fork-height", type=int, default=FORK_HEIGHT)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--classify-depth", type=int, default=60,
                    help="how many ranks to check for program ownership before taking the top N")
    ap.add_argument("--stamp", action="store_true", help="OpenTimestamp the snapshot after writing it")
    ap.add_argument("--ots-bin", default=OTS_BIN)
    # Default to the directory the /solanasnapshot page publishes from, so a
    # fork-time run needs no path argument and the files land where people can
    # download the exact bytes the digest covers.
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "solanasnapshot"))
    args = ap.parse_args()

    print("querying holders ...", file=sys.stderr)
    slot, totals, n_accounts = fetch_balances()
    print(f"  slot {slot}: {n_accounts} token accounts, {len(totals)} distinct owners", file=sys.stderr)

    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    candidates = [addr for addr, _ in ranked[:args.classify_depth]]
    print(f"classifying top {len(candidates)} owners ...", file=sys.stderr)
    programs = classify(candidates)

    # Record what each exclusion held and where it ranked. Excluding a pool is
    # right; excluding a multisig or custody vault would strip a real holder of
    # a claim, so every exclusion has to be auditable after the fact.
    rank_of = {addr: i for i, (addr, _) in enumerate(ranked, 1)}
    excluded = {addr: {"owned_by": prog,
                       "raw": totals[addr],
                       "balance": totals[addr] / 10 ** DECIMALS,
                       "rank_if_included": rank_of[addr]}
                for addr, prog in programs.items()}
    for addr, info in sorted(excluded.items(), key=lambda kv: kv[1]["rank_if_included"]):
        print(f"  excluded #{info['rank_if_included']} {addr} "
              f"({info['balance']:.6f}, owned by {info['owned_by']})", file=sys.stderr)

    eligible = [{"rank": i, "owner": addr, "raw": raw, "balance": raw / 10 ** DECIMALS}
                for i, (addr, raw) in enumerate(
                    [(a, r) for a, r in ranked if a not in programs][:args.top], 1)]
    pool_total = sum(row["raw"] for row in eligible)
    for row in eligible:
        row["share_of_top"] = row["raw"] / pool_total if pool_total else 0.0

    snapshot = {
        "mint": MINT,
        "token_program": TOKEN_2022,
        "solana_slot": slot,                          # when this was captured, not re-queryable
        "beta_fork_height": args.fork_height,
        "beta_fork_block_hash": args.fork_hash,       # unpredictable before the fork: proves "not early"
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "token_accounts": n_accounts,
        "distinct_owners": len(totals),
        "excluded_program_accounts": excluded,
        "top": eligible,
        "all_owners": dict(ranked),
    }

    canonical = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(canonical).hexdigest()

    base = f"{args.out.rstrip('/')}/sol-ecash-snapshot-slot{slot}"
    with open(base + ".json", "wb") as fh:
        fh.write(canonical)
    with open(base + ".csv", "w") as fh:
        fh.write("rank,owner,balance,share_of_top\n")
        for row in eligible:
            fh.write(f"{row['rank']},{row['owner']},{row['balance']:.6f},{row['share_of_top']:.8f}\n")

    print(f"\nslot {slot} | {len(totals)} owners | top {len(eligible)} wallets")
    for row in eligible:
        print(f" {row['rank']:2d} {row['owner']:<44} {row['balance']:15.6f}  {row['share_of_top'] * 100:5.2f}%")
    print(f"\nwrote {base}.json and {base}.csv")
    print(f"sha256 = {digest}")

    if args.stamp:
        stamp(base + ".json", args.ots_bin)
    else:
        print(f"\nto timestamp: python3 {sys.argv[0]} ... --stamp")


if __name__ == "__main__":
    main()
