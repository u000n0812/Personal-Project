"""Investor-sentiment indicators.

Two levels, kept separate on purpose:

* **Market mood** (``market``): a Fear & Greed index per market, built from
  price-based components — each scored against its own past year.
* **Company sentiment** (``sources`` → ``model.aggregate``): readings from
  independent source *families* — Crowd, News, Analysts, Positioning, Price —
  combined so no single community or data source can dominate.

Modules: ``model`` (data model + aggregation), ``text`` (headline/post
scoring), ``price`` (price behavior vs the market), ``market`` (Fear & Greed),
``sources`` (adapters: parsing is pure, fetching is separate), ``engine``
(orchestration), ``history`` (daily records), ``synthetic`` (demo data),
``collect`` (CLI for a daily cron). No Streamlit imports in this package.

Sentiment is a supplementary signal about investor psychology — not a
forecast, and at extremes often read contrarily.
"""
