import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { CLAIMED_LAMPORTS } from "./solrewards";

/**
 * The live holder ranking and creator fees, written every ~10 minutes by
 * scripts/sol-holder-live.py (systemd timer szats-sol-live). Unlike the
 * published snapshot this file is never hashed or timestamped: it is a moving
 * estimate of what a snapshot taken now would show.
 */

const LIVE_FILE = path.join(process.cwd(), "data", "sol-live.json");

/** Older than this and the page says the tracker has stopped updating. */
export const LIVE_STALE_SECONDS = 45 * 60;

export type LiveHolder = { rank: number; owner: string; balance: number; raw: number };

export type LiveData = {
    mint: string;
    solana_slot: number;
    captured_at_utc: string;
    token_accounts: number;
    distinct_owners: number;
    excluded_program_accounts: Record<string, { owned_by: string; balance: number; raw: number; rank_if_included: number }>;
    top: LiveHolder[];
    all_owners: Record<string, number>;
    creator_fees: {
        claimed_since_snapshot_lamports: number;
        claims_since_snapshot: number;
        unclaimed_lamports: number;
    };
    sol_usd: number | null;
    /** Absent in files written before prices were tracked; null when DexScreener had no answer. */
    prices?: { memecoin: MarketPrice | null; wecx: MarketPrice | null };
};

export type MarketPrice = { usd: number; dex: string | null; pair: string | null; liquidity_usd: number | null };

export type LiveLoaded = { data: LiveData; ageSeconds: number };

export async function loadLive(): Promise<LiveLoaded | null> {
    try {
        const [bytes, info] = await Promise.all([readFile(LIVE_FILE), stat(LIVE_FILE)]);
        const data = JSON.parse(bytes.toString()) as LiveData;
        if (!Array.isArray(data.top) || !data.creator_fees) return null;
        return { data, ageSeconds: Math.max(0, (Date.now() - info.mtimeMs) / 1000) };
    } catch {
        return null;
    }
}

/**
 * Lifetime creator fees now: the claims up to the beta snapshot (fixed facts in
 * solrewards.ts) plus everything the live run found since, plus what is still
 * unclaimed in the vaults.
 */
export function lifetimeFees(d: LiveData): { claimedBefore: bigint; claimedSince: bigint; unclaimed: bigint; total: bigint } {
    const claimedSince = BigInt(Math.round(d.creator_fees.claimed_since_snapshot_lamports));
    const unclaimed = BigInt(Math.round(d.creator_fees.unclaimed_lamports));
    return { claimedBefore: CLAIMED_LAMPORTS, claimedSince, unclaimed, total: CLAIMED_LAMPORTS + claimedSince + unclaimed };
}

/**
 * The ECX price the memecoin market implies. A top-15 holder's tokens are a
 * claim on the pool in proportion to their share of supply excluding pools, so
 * each token is worth pool / supply ECX, and the market price of a token
 * implies price x supply / pool per ECX — the memecoin's market cap (excluding
 * pools) over the projected pool.
 */
export function impliedEcxPrice(memecoinUsd: number, supplyExcludingPoolsRaw: number, poolEcxSzats: bigint, decimals = 6): number | null {
    const poolEcx = Number(poolEcxSzats) / 1e8;
    if (!(memecoinUsd > 0) || !(poolEcx > 0) || !(supplyExcludingPoolsRaw > 0)) return null;
    return (memecoinUsd * supplyExcludingPoolsRaw) / 10 ** decimals / poolEcx;
}

/** SOL price in cents, or null when the live run could not fetch one. */
export function solUsdCents(d: LiveData): bigint | null {
    return d.sol_usd && Number.isFinite(d.sol_usd) && d.sol_usd > 0 ? BigInt(Math.round(d.sol_usd * 100)) : null;
}
