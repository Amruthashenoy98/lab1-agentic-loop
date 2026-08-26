# Lab 4.3 - Scaling Output

Wired a news-monitoring pipeline (Helix Robotics headlines) to three patterns: batch processing, parallel calls, and multi-pass review.

## Exercise 1 - Message Batches API
Built one request per headline with a stable custom_id, then wrote the polling loop (retrieve, print status, break when ended, timeout fallback with a --fetch hint).

All 8 headlines came back correctly classified by sentiment, joined back up by custom_id (results returned out of submission order, which is expected for batches).

## Exercise 2 - Parallel Processing
Implemented run_parallel() using ThreadPoolExecutor with pool.map() to keep results in input order.

Sequential: 8.4s
Parallel: 2.9s
Speedup: ~2.9x

Since the work is I/O-bound (waiting on the API), threads overlap the waits and finish the same batch much faster.

## Exercise 3 - Multi-Pass Review
Implemented critique() (lists issues only, doesn't rewrite) and refine() (applies every point, outputs only the final text).

Draft was long, promotional in tone, and editorialized with a "good news / bad news" structure - over the word limit.
Critique caught all of it: too long, buries the lead, speculates beyond the headlines, leans positive, not neutral, editorializes in the closing line.
Refined version fixed every point - under the word limit, neutral tone, leads with the clearest fact, balances positive and negative coverage.
