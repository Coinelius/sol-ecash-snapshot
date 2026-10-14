#!/usr/bin/env python3
"""Recompute the beta snapshot's ECX allocation from the published JSON.

Standard library only. Mirrors lib/solshare.ts and lib/solrewards.ts exactly
(integer arithmetic, rounding down), so its output should match the
/solanasnapshot page to the satoshi.

    python3 scripts/verify_allocation.py snapshot/beta/sol-ecash-snapshot-slot448335648.json
"""
import hashlib
import json
import sys

# --- Creator rewards at the snapshot (Solana slot 448,335,648), all on chain. ---
# Every claim out of the coin's two creator vaults before the snapshot, in lamports.
CLAIMS_BEFORE_SNAPSHOT = {
    "37gCL2tfqygZDbagt4xXwsKZXE1xFQnbKHT18kvzbVf4tRBw6Jm5pCL3TZDXZ4whzfPgKPpjWTzztHdRsHD1oBT9": 31_471_847_843,
    "9P5x9U3nkQyksprwc5gVT8jtRGw9uQ3AUyzyAdGhzUTR9gkjExcqe6hgDik5U9RmhH3Fv9PdH74sWnnzBo1jVyK": 332_118_172_106,
    "a4iRLub3PV2WKyCFkEuSdLvCgRJjnAZWSum77V5aER2P4Kac3jCoV1mmj8NUiqxHJUvumKVLFbCf9WhtfxYQXTA": 90_314_570_798,
    "5TWAiabgRsAMHEXQgzqNT4SenbkEVTawrm9SdSkk43u8h9zJFSRPMhRo1XEhmiH9up8Ps5sgkiPwTxTkwE5ioovG": 205_470_720_166,
    "54SNsQCNMJfH7LYZmkXQNtWdePuLiQRFrgqAwz4m372ZmBt6F8irJWiAzDq7StrU4vsqVr2w51iMZtqhN7HKmoaG": 62_669_210_920,
    "JwxRzNYWeFXhhw1QXhRP2FZfzNkQrHnEv1k5GmperDmzL225iPmbM8y8VPBaxD1se9bqo1zDzVdtETVAYsWvCua": 104_145_125_835,
    "8VtFu6UhCmpGUS4hBDMwqgZrWxHBffib1jAUwkyd6xi2QPrgMt8fApkHafUaCumHW5DUiZsBVYyb8XqtYwJ7T2i": 15_767_719_330,
    "3yoFSnVkGodscxedsoSJ1BnVS2LsuuiS99WLPGxYBoVUKi7PqrRWyp8Jg7sXcwGeBpQzGbVDBGiSkoYQRB4b8bMW": 18_543_709_962,
    "3SRMosTuCDFcFy9jZX1o1ZS5n4rWb1n9h94Ja3T44Pd6gNrn541t31pihk7zzu7ZvGwZ5FgiBtcYCKXuQxch2xRT": 4_327_948_770,
}
UNCLAIMED_AT_SNAPSHOT = 9_411_471_721      # PumpSwap creator vault after slot 448,318,540
SOL_USD_CENTS = 11_207                     # Binance SOLUSDT 1-minute close, 2026-09-19 07:09 UTC
ECX_USD_CENTS = 3_000                      # programme reference price, ecash.com/sol-token

PUBLISHED_SHA256 = "4871b5264be69938dbda94baaa213488b4bd1e2961b8819cb51305eca12102ac"


def fmt_ecx(szats):
    return f"{szats // 10**8:,}.{szats % 10**8:08d}"


def main(path):
    raw = open(path, "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    print(f"sha256 {digest}  {'matches' if digest == PUBLISHED_SHA256 else 'DOES NOT MATCH'} the published digest")
    snap = json.loads(raw)

    # Denominator: every owner (pools included, sums to the mint supply) less the program-owned pool accounts.
    total = sum(snap["all_owners"].values())
    pools = sum(a["raw"] for a in snap["excluded_program_accounts"].values())
    supply = total - pools
    print(f"supply {total / 1e6:,.6f} - pools {pools / 1e6:,.6f} = {supply / 1e6:,.6f} tokens (excluding pools)")

    lamports = sum(CLAIMS_BEFORE_SNAPSHOT.values()) + UNCLAIMED_AT_SNAPSHOT
    usd_cents = lamports * SOL_USD_CENTS // 10**9
    pool = lamports * SOL_USD_CENTS * 10**8 // (10**9 * ECX_USD_CENTS)
    print(f"creator rewards {lamports / 1e9:,.9f} SOL = ${usd_cents // 100:,}.{usd_cents % 100:02d} -> pool {fmt_ecx(pool)} ECX\n")

    print(f"{'#':>2}  {'wallet':44}  {'share':>7}  {'ECX':>16}")
    allocated = 0
    for h in snap["top"]:
        ecx = pool * h["raw"] // supply
        allocated += ecx
        print(f"{h['rank']:>2}  {h['owner']:44}  {100 * h['raw'] / supply:6.2f}%  {fmt_ecx(ecx):>16}")
    print(f"\nallocated to the top {len(snap['top'])}: {fmt_ecx(allocated)} ECX; "
          f"not allocated (supply held outside the top {len(snap['top'])}): {fmt_ecx(pool - allocated)} ECX")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "snapshot/beta/sol-ecash-snapshot-slot448335648.json")
