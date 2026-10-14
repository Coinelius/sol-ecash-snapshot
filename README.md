# sol-eCash holder snapshot

The holder snapshot of the pump.fun **$eCash** memecoin on Solana
(`cTxqg4vt21u1Q2f9DSEig6S1fxmxLSsUV2v2wWspump`), the logic that turns it into an
ECX allocation, and everything needed to check both yourself.

Published at **https://szats.world/solanasnapshot**, which also has a live tracker
(what a snapshot taken now would show) and the mainnet snapshot once eCash mainnet
forks.

This is a community-run service, not affiliated with LayerTwo Labs or ecash.com.

## Contents

| Path | What it is |
|---|---|
| `snapshot/beta/sol-ecash-snapshot-slot448335648.json` | The beta snapshot, exactly as published (canonical JSON) |
| `snapshot/beta/…json.ots` | Its OpenTimestamps proof, anchored in Bitcoin |
| `snapshot/beta/…csv` | The top 15 in CSV form |
| `scripts/sol-holder-snapshot.py` | The capture script that produced the snapshot |
| `scripts/sol-holder-live.py` | The live tracker behind the site's Live tab |
| `scripts/verify_allocation.py` | Recomputes every published number from the JSON (standard library only) |
| `lib/solshare.ts` | Allocation weighting (share of supply excluding pools) |
| `lib/solrewards.ts` | Creator rewards at the snapshot, the ECX pool, per-holder ECX |
| `lib/sollive.ts` | Live tracker maths: lifetime fees, implied ECX price |

## The beta snapshot

| | |
|---|---|
| Solana slot | **448,335,648** |
| Captured | **2026-09-19 07:09:35 UTC** |
| Beta fork block | **967,680**, hash `00000000000000030101ba5cfea54b22becc79f95dc6040beb76e01dd9d04042` |
| Holders | 3,732 owners across 3,755 token accounts |
| SHA-256 of the JSON | `4871b5264be69938dbda94baaa213488b4bd1e2961b8819cb51305eca12102ac` |
| Anchored in Bitcoin | block **967,682** (2026-09-19 07:22:39 UTC), 13 minutes after capture |

### How it was captured

`sol-holder-snapshot.py` ran the moment the eCash beta fork block existed, against the
free public Solana RPC (no API key, no third-party indexer):

1. **Every token account for the mint** via one `getProgramAccounts` call. The mint is
   **Token-2022**, so the query targets that program, and filters on the mint alone:
   Token-2022 accounts vary in size, so the usual `dataSize: 165` filter would silently
   drop holders. Only owner and amount are fetched (`dataSlice`).
2. **Balances are summed per owner**, since one wallet can hold through several token
   accounts.
3. **Program-owned accounts are excluded.** A liquidity pool holds tokens on behalf of its
   depositors and is not a holder. Each exclusion is recorded in the JSON with its
   balance, the program that owns it, and the rank it would otherwise have taken, so
   every exclusion can be audited. Three were excluded: the PumpSwap pool (rank 2 if
   counted, owned by `pAMMBay6…`), a Meteora DLMM pool (rank 44, `LBUZKhRx…`) and a pool
   owned by program `AveaiuA1…` (rank 41).
4. **The top 15 remaining wallets** are listed, and **every owner's raw balance** is kept
   in `all_owners`, so the denominator below can be recomputed by anyone.
5. The JSON is written in canonical form (sorted keys, no whitespace), hashed, and
   stamped with OpenTimestamps.

## The ECX allocation

### Weighting

Each of the top 15 wallets is weighted by its **share of the coin's whole supply
excluding liquidity pools**, not by its share of the top 15:

```
supply excluding pools = sum(all_owners) − sum(excluded pool accounts)
                       = 999,875,018.735865 − 108,683,667.123615
                       = 891,191,351.612250 tokens

holder's ECX = floor(pool × holder's raw balance ÷ supply excluding pools)
```

The 15 shares therefore sum to 84.93%, not 100%: the rest of the supply sits with
holders outside the top 15, and the ECX corresponding to it (492.21 ECX at the beta
snapshot) is not allocated.

### Pool size: creator rewards ÷ $30

The pool is the coin's **lifetime creator rewards** at the snapshot, in dollars, divided
by the **$30 reference price** (ecash.com/sol-token), capped at **50,000 ECX**.

The creator rewards were read from Solana, not from pump.fun's interface, which has no
historical view:

- The coin's creator is a **pump.fun fee-sharing config**,
  `D5KNhoQ8Bg7vRGncKMrDDNpGpskFTJt9PNQWm5L9Y2BS`, created three slots after the coin
  (slot 415,602,879 vs 415,602,876). So **every creator fee the coin has earned went
  through its two vaults**:
  - PumpSwap: `CC1HWdnWsok4zBHTUySipZU6rBrZtYvrN9q7cz2784ai` (wrapped SOL)
  - bonding curve: `DhMkWPV69kVhkUWsTDmENjUkwwRrsFo3MNzwMLC6hRfr`
- Its sole shareholder (100%, admin revoked) is
  `AZAQQsLehoqJawgT1dZjYuicZZG12uPCkoFGufwitkBu`.
- **Claimed before the snapshot:** 9 claims, **864.829025730 SOL** (lamports leaving the
  vaults in each; signatures in `lib/solrewards.ts` and `scripts/verify_allocation.py`).
  Earlier claims into the same wallet from another coin's fee config
  (`TnRB4KE9…pump`, 141.78 SOL) are **not** this coin's fees and are excluded.
- **Unclaimed at the snapshot:** **9.411471721 SOL** in the PumpSwap vault (its balance
  after slot 448,318,540, its last transaction before the snapshot).
- **Total: 874.240497451 SOL × $112.07** (Binance SOLUSDT, the snapshot minute)
  **= $97,976.13 → 3,265.87108497 ECX** (6.53% of the 50,000 cap).

All arithmetic is integer and rounds down, so no holder is ever allocated more than
their share and the total is never exceeded.

## Verify it yourself

```sh
# 1. The file is the one that was published
sha256sum snapshot/beta/sol-ecash-snapshot-slot448335648.json
# 4871b5264be69938dbda94baaa213488b4bd1e2961b8819cb51305eca12102ac

# 2. It existed before Bitcoin block 967,682 (2026-09-19 07:22:39 UTC)
npm install -g opentimestamps     # or: pip install opentimestamps-client
ots verify snapshot/beta/sol-ecash-snapshot-slot448335648.json.ots

# 3. Every allocation number
python3 scripts/verify_allocation.py
```

**What the proofs establish:**

- **Not before the fork:** the JSON embeds beta block 967,680's hash, which nobody could
  know before that block was mined.
- **Not after 07:22:39 UTC:** OpenTimestamps put the file's SHA-256 into a Bitcoin
  transaction (paid for by the public calendar servers); the proof links the file to
  Bitcoin block 967,682.
- **Not edited since:** any change to the file changes its SHA-256.

**What they do not establish:** that the list faithfully reflects Solana state at that
slot. `getProgramAccounts` has no historical mode, so the slot cannot be re-queried later.
The snapshot was published immediately so anyone could compare it with their own taken at
the same time.

## The live tracker

`sol-holder-live.py` runs every 10 minutes on the site and writes a JSON file the Live tab
reads (it is never hashed or timestamped: it is a moving estimate). It:

- ranks holders with **the capture script's own functions**, so the two cannot drift;
- tracks **lifetime creator fees** as they grow: the pre-snapshot claims above, plus claims
  since the snapshot (found by scanning the shareholder wallet's new transactions), plus
  what is unclaimed in the vaults now, valued at the live SOL price;
- records market prices for the memecoin and wECX from their most liquid DexScreener pairs.

The **ECX price implied by the memecoin** follows from the weighting: each token held by a
top-15 wallet is a claim on `pool ÷ supply excluding pools` ECX, so

```
implied ECX price = memecoin price × supply excluding pools ÷ pool ECX
```

i.e. the memecoin's market cap (excluding pools) over the projected pool.

## The mainnet snapshot

Taken the same way when eCash mainnet forks from Bitcoin at block **973,728**, embedding
that block's hash, stamped with OpenTimestamps, and published at
https://szats.world/solanasnapshot?tab=mainnet and in `snapshot/mainnet/` here.
