# Differential oracle

For each fixed mutation, strategy_comparison.json records authorized scope,
strict runtime cell diff, conservative semantic diff, all changed decompressed
ZIP members, XML unified diffs, cached answer-value projection, official score,
and post-recalculation answer differences from the retained candidate.

Official labels are joined only by the offline protocol module. The runtime
adapter imports neither sb nor evaluate and never receives golden paths/values.
Cached answer projection cannot establish indirect formula propagation; only the
offline official recalculation comparison establishes that observation.

Package comparison measures decompressed member identity, not entire ZIP binary
identity. Recompression can change container bytes without changing member bytes.
The raw method additionally preserves all worksheet bytes outside selected cells.
Semantic coverage limits are stated in PRESERVATION_CONTRACT.md.

Latency for the retained ordinary candidate is file-copy time, not historical
save latency. It must not be compared as an algorithm speed measurement. Other
strategy latencies measure reconstruction only. Tokens and additional model
actions are zero; each replay represents one retained mutation. Official scoring
and rendering are separate offline costs. Invalid strategies remain in results.

Local LibreOffice recalculation failed during the first replay; the partial
artifacts are retained under offline/. Cached-only results are explicitly marked
recalculation_enabled=false and are not official benchmark success claims.
