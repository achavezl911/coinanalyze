# Patches applied v1.2.3

## AI context API

- Added `/api/ai/context` for one-symbol compact AI payload generation.
- Added `/api/ai/context/bundle` for multi-symbol compact AI payload generation.
- Added `/api/ai/profiles` to document `lite`, `default`, and `pro` payload profiles.
- Payload includes data confidence, compact snapshot, scalp summary, operator read, local risk alerts, delta matrix, orderbook, liquidation levels, recent signals, and rough token estimate.
- The endpoint is internal-token protected like the rest of `/api/*`.
- No secrets are emitted by the AI context endpoint.

## Goal

The bridge no longer needs to infer or over-fetch from multiple endpoints. This API exposes a stable, versioned, compact contract for downstream AI analysis.
