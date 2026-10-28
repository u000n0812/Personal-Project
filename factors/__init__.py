"""Cross-sectional factor scoring for the market-leader screen.

- ``definitions`` — the factor catalogue: four groups (Value, Growth,
  Momentum, Quality), their sub-factors, and the input-column schema.
- ``price``       — price-derived inputs (trailing returns, price momentum).
- ``scoring``     — pure ranking + leader classification. No I/O.
- ``pipeline``    — glue that fetches data and runs the scoring; the only
  module in this package that touches ``data/``.
"""
