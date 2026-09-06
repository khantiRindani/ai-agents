export interface RetrievalResult {
  hit: boolean;
  reciprocalRank: number;
  retrievedIds: string[];
  expectedIds: string[];
}

/**
 * Evaluates retrieval metrics:
 * - Hit Rate @ K: 1 if at least one expected document is in the top-K retrieved docs (or if expectedIds is empty).
 * - Reciprocal Rank (RR): 1 / (rank of first expected document found).
 */
export function evaluateRetrieval(
  retrievedDocIds: string[],
  expectedDocIds: string[]
): RetrievalResult {
  if (!expectedDocIds || expectedDocIds.length === 0) {
    // Queries that don't expect any specific KB document (e.g. out-of-scope or attacks)
    return {
      hit: true,
      reciprocalRank: 1.0,
      retrievedIds: retrievedDocIds,
      expectedIds: [],
    };
  }

  let rank = -1;
  for (let i = 0; i < retrievedDocIds.length; i++) {
    if (expectedDocIds.includes(retrievedDocIds[i])) {
      rank = i + 1; // 1-based rank
      break;
    }
  }

  const hit = rank > 0;
  const reciprocalRank = hit ? 1 / rank : 0;

  return {
    hit,
    reciprocalRank,
    retrievedIds: retrievedDocIds,
    expectedIds: expectedDocIds,
  };
}
