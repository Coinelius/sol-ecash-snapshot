/**
 * Allocation weighting.
 *
 * A holder's share is of the coin's entire supply excluding liquidity pools —
 * not of the top-15 pool. The top 15 are only who may register; they are not
 * the denominator. The distinction is large: rank 1 is 48.36% of the top-15
 * pool but 41.07% of supply excluding pools, and the fifteen shares sum to
 * 0.8493 rather than 1.
 *
 * `all_owners` in the snapshot is the **pre-classification** total, so it
 * already contains the pool accounts — it sums exactly to the mint's
 * `getTokenSupply`. They are therefore subtracted here rather than assumed
 * absent, which is the trap: the pool owners are keyed in `all_owners` by the
 * account address, while `excluded_program_accounts[].owned_by` names the
 * owning program, so looking them up by `owned_by` finds nothing and makes the
 * pools look already-removed.
 *
 * No Node imports, so both the page and the API route can use one copy rather
 * than each deriving a denominator and drifting apart.
 */

export type PoolAccount = { raw: number };

/**
 * Total units held by real holders: every owner, less the program-owned pool
 * accounts. Raw integer units — well inside float range here (~1e15 against a
 * 9.007e15 safe-integer ceiling), so ordinary arithmetic is exact.
 */
export function supplyExcludingPools(
    allOwners: Record<string, number>,
    excluded: Record<string, PoolAccount>,
): number {
    const total = Object.values(allOwners).reduce((sum, raw) => sum + raw, 0);
    const pools = Object.values(excluded).reduce((sum, account) => sum + account.raw, 0);
    return total - pools;
}

/** A holder's fraction of supply excluding pools. */
export function shareOfSupply(raw: number, supply: number): number {
    return supply > 0 ? raw / supply : 0;
}
