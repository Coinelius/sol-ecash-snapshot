#!/usr/bin/env python3
"""Live counterpart of sol-holder-snapshot.py, for the /solanasnapshot "Live" tab.

Every run (a systemd timer, every ~10 min) writes data/sol-live.json with:

* the current holder ranking, computed exactly as the snapshot computes it —
  the same functions are imported from sol-holder-snapshot.py, so the two can
  never drift: every token account summed per owner, program-owned accounts
  (pools) excluded and listed, top 15 kept, all owners' raw balances included
  so the page can derive the supply-excluding-pools denominator itself;
* the coin's lifetime creator fees as they stand now: what was claimed out of
  the creator vaults after the beta snapshot (found by scanning the fee
  shareholder's transactions, cached in data/sol-live-state.json so each run
  only fetches what is new), plus what sits unclaimed in the vaults right now.
  The claims before the snapshot are not repeated here: they are fixed facts
  that live in src/lib/solrewards.ts, which the page adds in;
* the SOL/USD price at capture, to value those fees.

This file is NOT the published snapshot and is not hashed or timestamped. It
is a moving estimate, and the page labels it as one.

Usage: python3 scripts/sol-holder-live.py [--out data/sol-live.json]
"""

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_spec = importlib.util.spec_from_file_location("solsnap", os.path.join(HERE, "sol-holder-snapshot.py"))
solsnap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(solsnap)
rpc, fetch_balances, classify = solsnap.rpc, solsnap.fetch_balances, solsnap.classify

# The coin's creator is a pump.fun fee-sharing config whose sole shareholder is
# FEE_WALLET; every claim out of the two vaults is paid to it. See solrewards.ts.
FEE_WALLET = "AZAQQsLehoqJawgT1dZjYuicZZG12uPCkoFGufwitkBu"
VAULT_PUMPSWAP = "CC1HWdnWsok4zBHTUySipZU6rBrZtYvrN9q7cz2784ai"   # WSOL token account
VAULT_BONDING = "DhMkWPV69kVhkUWsTDmENjUkwwRrsFo3MNzwMLC6hRfr"    # plain SOL account
VAULTS = {VAULT_PUMPSWAP, VAULT_BONDING}
RENT_EXEMPT_ZERO_DATA = 890_880                                  # lamports a 0-byte account must keep
SNAPSHOT_SLOT = 448_335_648                                      # beta snapshot; claims up to here are in solrewards.ts


def claims_since_snapshot(state):
    """Lamports claimed out of the creator vaults after the beta snapshot. Cached per signature."""
    seen = state.setdefault("claims", {})          # signature -> lamports debited from the vaults
    newest_known = state.get("newest_sig")
    sigs, before = [], None
    while True:
        params = {"limit": 1000}
        if before:
            params["before"] = before
        if newest_known:
            params["until"] = newest_known
        page = rpc("getSignaturesForAddress", [FEE_WALLET, params])
        if not page:
            break
        sigs += page
        if len(page) < 1000 or page[-1]["slot"] <= SNAPSHOT_SLOT:
            break
        before = page[-1]["signature"]
    if sigs:
        state["newest_sig"] = sigs[0]["signature"]
    for s in sigs:
        if s["slot"] <= SNAPSHOT_SLOT or s["err"] is not None or s["signature"] in seen:
            continue
        tx = rpc("getTransaction", [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}])
        if not tx:
            continue
        keys = list(tx["transaction"]["message"]["accountKeys"])
        loaded = tx["meta"].get("loadedAddresses") or {}
        keys += loaded.get("writable", []) + loaded.get("readonly", [])
        pre, post = tx["meta"]["preBalances"], tx["meta"]["postBalances"]
        debited = sum(pre[i] - post[i] for i, k in enumerate(keys) if k in VAULTS and pre[i] > post[i])
        seen[s["signature"]] = debited
    return sum(seen.values())


def unclaimed_now():
    """Lamports sitting in the two creator vaults right now."""
    wsol = rpc("getTokenAccountBalance", [VAULT_PUMPSWAP])["value"]["amount"]
    bonding = rpc("getBalance", [VAULT_BONDING])["value"]
    return int(wsol) + max(0, bonding - RENT_EXEMPT_ZERO_DATA)


def sol_usd():
    """SOL/USDT last price from Binance; None if unreachable (the page then shows SOL only)."""
    try:
        req = urllib.request.Request("https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT",
                                     headers={"User-Agent": "szats.world"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return float(json.load(r)["price"])
    except Exception:
        return None


WECX_MINT = "6ombVv3YMs9qpx1QkycD9XW8HKSfv7vGrCFX3cxCYMVY"   # wrapped ECX (pre-market) on Solana


def market_price(mint):
    """USD price of `mint` from its most liquid DexScreener pair, or None.

    Only pairs where the token is the base are used, so the price is always
    "USD per one of this token", never inverted.
    """
    try:
        req = urllib.request.Request(f"https://api.dexscreener.com/latest/dex/tokens/{mint}",
                                     headers={"User-Agent": "szats.world"})
        with urllib.request.urlopen(req, timeout=20) as r:
            pairs = json.load(r).get("pairs") or []
    except Exception:
        return None
    pairs = [p for p in pairs if p.get("baseToken", {}).get("address") == mint and p.get("priceUsd")]
    if not pairs:
        return None
    best = max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)
    return {"usd": float(best["priceUsd"]), "dex": best.get("dexId"), "pair": best.get("pairAddress"),
            "liquidity_usd": (best.get("liquidity") or {}).get("usd")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "sol-live.json"))
    ap.add_argument("--state", default=os.path.join(ROOT, "data", "sol-live-state.json"))
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--classify-depth", type=int, default=60)
    args = ap.parse_args()

    slot, totals, n_accounts = fetch_balances()
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    programs = classify([a for a, _ in ranked[:args.classify_depth]])
    rank_of = {a: i for i, (a, _) in enumerate(ranked, 1)}
    excluded = {a: {"owned_by": p, "raw": totals[a], "balance": totals[a] / 10 ** solsnap.DECIMALS,
                    "rank_if_included": rank_of[a]} for a, p in programs.items()}
    top = [{"rank": i, "owner": a, "raw": r, "balance": r / 10 ** solsnap.DECIMALS}
           for i, (a, r) in enumerate([(a, r) for a, r in ranked if a not in programs][:args.top], 1)]

    try:
        state = json.load(open(args.state))
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    claimed_after = claims_since_snapshot(state)
    unclaimed = unclaimed_now()

    live = {
        "mint": solsnap.MINT,
        "solana_slot": slot,
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "token_accounts": n_accounts,
        "distinct_owners": len(totals),
        "excluded_program_accounts": excluded,
        "top": top,
        "all_owners": dict(ranked),
        "creator_fees": {
            "claimed_since_snapshot_lamports": claimed_after,
            "claims_since_snapshot": sum(1 for v in state["claims"].values() if v > 0),
            "unclaimed_lamports": unclaimed,
        },
        "sol_usd": sol_usd(),
        # Market prices for the page's price strip: the memecoin (to derive the
        # ECX price its holders' claim implies) and wECX, which trades directly.
        "prices": {"memecoin": market_price(solsnap.MINT), "wecx": market_price(WECX_MINT)},
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    for path, obj in ((args.state, state), (args.out, live)):
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(obj, fh, separators=(",", ":"))
        os.replace(tmp, path)       # readers never see a half-written file
    print(f"slot {slot}: {len(totals)} owners, top {len(top)}, claimed since snapshot "
          f"{claimed_after / 1e9:.4f} SOL, unclaimed {unclaimed / 1e9:.4f} SOL, SOL ${live['sol_usd']}")


if __name__ == "__main__":
    main()
