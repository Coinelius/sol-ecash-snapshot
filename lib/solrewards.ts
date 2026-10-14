/**
 * Creator rewards behind the ECX distribution, as they stood at the snapshot
 * (Solana slot 448,335,648, 2026-09-19 07:09:35 UTC).
 *
 * Read from chain rather than taken from pump.fun's UI, which has no
 * historical view. The coin's creator is a pump.fun fee-sharing config
 * (D5KNhoQ8Bg7vRGncKMrDDNpGpskFTJt9PNQWm5L9Y2BS, created three slots after the
 * mint), so every creator fee the coin has earned passed through its two
 * vaults. Total at the snapshot = what was claimed out of them before the
 * slot + what still sat in them at the slot.
 *
 * No Node imports: the page and any API route share this one copy.
 */

export type RewardClaim = { slot: number; signature: string; lamports: bigint };

/** Fee vaults of the coin's creator config: PumpSwap (WSOL) and bonding curve. */
export const CREATOR_VAULTS = {
    pumpSwap: "CC1HWdnWsok4zBHTUySipZU6rBrZtYvrN9q7cz2784ai",
    bondingCurve: "DhMkWPV69kVhkUWsTDmENjUkwwRrsFo3MNzwMLC6hRfr",
} as const;

export const CREATOR_CONFIG = "D5KNhoQ8Bg7vRGncKMrDDNpGpskFTJt9PNQWm5L9Y2BS";

/**
 * Every claim out of those vaults before the snapshot, as lamports leaving the
 * vaults in that transaction. All went to the config's sole shareholder.
 */
export const CLAIMS_BEFORE_SNAPSHOT: RewardClaim[] = [
    { slot: 417334064, signature: "37gCL2tfqygZDbagt4xXwsKZXE1xFQnbKHT18kvzbVf4tRBw6Jm5pCL3TZDXZ4whzfPgKPpjWTzztHdRsHD1oBT9", lamports: 31_471_847_843n },
    { slot: 418047724, signature: "9P5x9U3nkQyksprwc5gVT8jtRGw9uQ3AUyzyAdGhzUTR9gkjExcqe6hgDik5U9RmhH3Fv9PdH74sWnnzBo1jVyK", lamports: 332_118_172_106n },
    { slot: 419899415, signature: "a4iRLub3PV2WKyCFkEuSdLvCgRJjnAZWSum77V5aER2P4Kac3jCoV1mmj8NUiqxHJUvumKVLFbCf9WhtfxYQXTA", lamports: 90_314_570_798n },
    { slot: 424566398, signature: "5TWAiabgRsAMHEXQgzqNT4SenbkEVTawrm9SdSkk43u8h9zJFSRPMhRo1XEhmiH9up8Ps5sgkiPwTxTkwE5ioovG", lamports: 205_470_720_166n },
    { slot: 426533016, signature: "54SNsQCNMJfH7LYZmkXQNtWdePuLiQRFrgqAwz4m372ZmBt6F8irJWiAzDq7StrU4vsqVr2w51iMZtqhN7HKmoaG", lamports: 62_669_210_920n },
    { slot: 435809013, signature: "JwxRzNYWeFXhhw1QXhRP2FZfzNkQrHnEv1k5GmperDmzL225iPmbM8y8VPBaxD1se9bqo1zDzVdtETVAYsWvCua", lamports: 104_145_125_835n },
    { slot: 438541987, signature: "8VtFu6UhCmpGUS4hBDMwqgZrWxHBffib1jAUwkyd6xi2QPrgMt8fApkHafUaCumHW5DUiZsBVYyb8XqtYwJ7T2i", lamports: 15_767_719_330n },
    { slot: 440306471, signature: "3yoFSnVkGodscxedsoSJ1BnVS2LsuuiS99WLPGxYBoVUKi7PqrRWyp8Jg7sXcwGeBpQzGbVDBGiSkoYQRB4b8bMW", lamports: 18_543_709_962n },
    { slot: 441213412, signature: "3SRMosTuCDFcFy9jZX1o1ZS5n4rWb1n9h94Ja3T44Pd6gNrn541t31pihk7zzu7ZvGwZ5FgiBtcYCKXuQxch2xRT", lamports: 4_327_948_770n },
];

/** Unclaimed in the PumpSwap vault at the snapshot: its balance after slot 448,318,540, its last transaction before the snapshot. */
export const UNCLAIMED_AT_SNAPSHOT_LAMPORTS = 9_411_471_721n;

/** SOL/USD at 07:09 UTC on 2026-09-19, the snapshot minute: Binance SOLUSDT 1-minute close. In cents. */
export const SOL_USD_CENTS = 11_207n;

/** The ECX base price the distribution is denominated at. In cents. */
export const ECX_USD_CENTS = 3_000n;

const LAMPORTS_PER_SOL = 1_000_000_000n;
const SZATS_PER_ECX = 100_000_000n;

export const CLAIMED_LAMPORTS = CLAIMS_BEFORE_SNAPSHOT.reduce((sum, claim) => sum + claim.lamports, 0n);
export const CREATOR_REWARDS_LAMPORTS = CLAIMED_LAMPORTS + UNCLAIMED_AT_SNAPSHOT_LAMPORTS;

/** Creator rewards in US cents at the snapshot price, rounded down. */
export const CREATOR_REWARDS_USD_CENTS = (CREATOR_REWARDS_LAMPORTS * SOL_USD_CENTS) / LAMPORTS_PER_SOL;

/**
 * ECX to distribute, in szats: the rewards' dollar value at the ECX base price.
 * Worked from lamports in one division so no intermediate rounding creeps in.
 */
export const TOTAL_ECX_SZATS =
    (CREATOR_REWARDS_LAMPORTS * SOL_USD_CENTS * SZATS_PER_ECX) / (LAMPORTS_PER_SOL * ECX_USD_CENTS);

/**
 * A holder's ECX, in szats: their share of supply excluding pools (raw units
 * over that supply, as in `solshare.ts`) of the total, rounded down.
 */
export function ecxForHolder(raw: number, supplyExcludingPools: number, totalSzats: bigint = TOTAL_ECX_SZATS): bigint {
    if (supplyExcludingPools <= 0) return 0n;
    return (totalSzats * BigInt(Math.round(raw))) / BigInt(Math.round(supplyExcludingPools));
}

/** The programme's ceiling on the swap pool, per ecash.com/sol-token. */
export const POOL_MAX_ECX = 50_000n;
const POOL_MAX_SZATS = POOL_MAX_ECX * SZATS_PER_ECX;

/**
 * The ECX pool for any amount of creator fees at a given SOL price: their
 * dollar value at the ECX reference price, capped at POOL_MAX_ECX. The beta
 * snapshot's TOTAL_ECX_SZATS is this at the snapshot's figures (far below the cap).
 */
export function poolSzats(lamports: bigint, solUsdCents: bigint): { szats: bigint; capped: boolean } {
    const uncapped = (lamports * solUsdCents * SZATS_PER_ECX) / (LAMPORTS_PER_SOL * ECX_USD_CENTS);
    return uncapped > POOL_MAX_SZATS ? { szats: POOL_MAX_SZATS, capped: true } : { szats: uncapped, capped: false };
}

/** Lamports at a SOL price, in US cents, rounded down. */
export function lamportsToUsdCents(lamports: bigint, solUsdCents: bigint): bigint {
    return (lamports * solUsdCents) / LAMPORTS_PER_SOL;
}

/** Szats of ECX valued at the reference price, in US cents. */
export function ecxToUsdCents(szats: bigint): bigint {
    return (szats * ECX_USD_CENTS) / SZATS_PER_ECX;
}

/** Szats as a decimal ECX string with all eight places. */
export function formatEcx(szats: bigint): string {
    const whole = szats / SZATS_PER_ECX;
    const frac = (szats % SZATS_PER_ECX).toString().padStart(8, "0");
    return `${whole.toLocaleString("en-US")}.${frac}`;
}

/** Cents as dollars with two places. */
export function formatUsd(cents: bigint): string {
    return `$${(cents / 100n).toLocaleString("en-US")}.${(cents % 100n).toString().padStart(2, "0")}`;
}

/** Lamports as SOL with all nine places. */
export function formatSol(lamports: bigint): string {
    const whole = lamports / LAMPORTS_PER_SOL;
    return `${whole.toLocaleString("en-US")}.${(lamports % LAMPORTS_PER_SOL).toString().padStart(9, "0")}`;
}
