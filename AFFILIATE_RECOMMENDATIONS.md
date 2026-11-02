# Rocket21 recommendations — 2 November 2026

Tong approved starting with 2 links per new post, different categories, in
2 separate disclosed comments. The existing auto_affiliate workflow remains
the only writer. Threads keeps its existing behavior.

Facebook uses recommendation_count=2 and recommendation_pool. Choose the least
used product first, then a product in another category; break ties by oldest
use. SubID1 is rp123 (WARRIX polo), rp124 (X-GORiLLA case), rp125 (LACANA perfume).
All three links were generated in Tong's Shopee Affiliate UI and returned 301
to the expected shop/item with the correct utm_content product code. This is
an audience experiment, not evidence of buyer demand or physical testing.
The registry's legacy rp category is a catch-all; actual categories are stored
in recommendation_pool and registry notes.

recommendations_since limits this mode to new posts after activation. Existing
comments and completed legacy state are preserved. Exact per-post mappings
still take precedence and remain one reviewed recommendation.

Each slot is reserved durably before publishing. A definite server rejection
allows only that slot to retry. Timeouts, missing IDs and failed verification
hold the slot. Recover only from the same product URL in an actual own reply;
never infer the second product was sent because the first reply exists.
No pictures, prices, performance or authenticity claims are fabricated.

Validation: 40 tests passed, including 5 recommendation tests covering category
rotation, reruns, dry-run, partial timeouts/recovery and definite rejection.
Live API dry-run verified account 111830598532037 (Rocket21); all 50 fetched
posts predated activation, so no comments were written during validation.

The central registry was updated to 54 active products. Exported legacy
workbooks were NOT deployed: remote workbooks contain 71 rows while the
registry export contains 54. Preserve that unrelated inventory until separately
reconciled. The new comment worker reads the verified JSON recommendation pool.

To turn off the optional runner, remove recommendation_count from the Facebook
config; legacy completed state remains readable. Do not delete or reset state.
