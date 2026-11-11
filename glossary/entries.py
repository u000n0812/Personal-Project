"""Dictionary content. Plain data — edit freely; see glossary/__init__.py.

Formulas are LaTeX (rendered with KaTeX). Field guide:

    definition   one-paragraph plain-language definition (required)
    measures     what a metric tells you (metrics only)
    formula      LaTeX formula (metrics / calculations only)
    example      worked numeric example
    interpret    how to read it: higher vs lower, caveats
    in_app       how this app computes or uses it — keep in sync with the code
    related      ids of related entries
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    id: str
    term: str
    category: str
    definition: str
    aliases: tuple[str, ...] = ()
    korean: str = ""
    measures: str = ""
    formula: str = ""
    example: str = ""
    interpret: str = ""
    in_app: str = ""
    related: tuple[str, ...] = ()

    @property
    def summary(self) -> str:
        """First sentence of the definition."""
        first = self.definition.split(". ")[0]
        return first if first.endswith(".") else first + "."

    @property
    def searchable_text(self) -> str:
        return " ".join((self.definition, self.measures, self.interpret,
                         self.in_app, self.example)).casefold()


FACTORS = "Factors & scoring"
VALUE = "Value metrics"
GROWTH = "Growth metrics"
MOMENTUM = "Momentum metrics"
QUALITY = "Quality metrics"
LEADERS = "Market leaders"
BACKTEST = "Backtesting"
PORTFOLIO = "Portfolio"
SECTORS = "Sectors & ETFs"
DATA = "Markets & data"
BASICS = "Financial statement basics"

CATEGORIES = (FACTORS, VALUE, GROWTH, MOMENTUM, QUALITY, LEADERS, BASICS,
              PORTFOLIO, BACKTEST, SECTORS, DATA)


ENTRIES: tuple[Entry, ...] = (
    # =====================================================================
    # Factors & scoring
    # =====================================================================
    Entry(
        "factor", "Factor", FACTORS, korean="팩터",
        definition="A measurable characteristic of a stock that has historically helped "
                   "explain why some stocks earn higher returns than others. Factor "
                   "investing ranks stocks on such characteristics instead of judging "
                   "each company one by one.",
        in_app="The app uses four factor groups — Value, Growth, Momentum and Quality — "
               "each built from several metrics.",
        related=("value-factor", "growth-factor", "momentum-factor", "quality-factor",
                 "factor-score"),
    ),
    Entry(
        "value-factor", "Value factor", FACTORS, korean="가치 팩터",
        definition="Favors stocks that are cheap relative to their earnings, assets, cash "
                   "flow or dividends. The idea: in the short run the market can misprice "
                   "a company, so buying below intrinsic worth and waiting for the price "
                   "to catch up earns excess returns.",
        interpret="Cheap stocks can stay cheap for long periods (a value trap), so value "
                  "works best confirmed by other factors.",
        in_app="Built from earnings yield, dividend yield, book-to-market and cash-flow "
               "yield, each ranked higher-is-better.",
        related=("earnings-yield", "dividend-yield", "book-to-market", "cash-flow-yield",
                 "pe", "pb", "value-trap"),
    ),
    Entry(
        "growth-factor", "Growth factor", FACTORS, korean="성장 팩터",
        definition="Favors companies whose sales and profits are expected to grow. A "
                   "share price is EPS × P/E, and growth can lift both: earnings rise, and "
                   "investors pay a higher multiple for them. Growth matters most when "
                   "interest rates are low, because future profits are discounted less.",
        in_app="Built from forward revenue revision, operating-margin change, forward EPS "
               "growth and long-term (sustainable) growth.",
        related=("revenue-revision", "op-margin-change", "eps-growth", "long-term-growth",
                 "operating-leverage"),
    ),
    Entry(
        "momentum-factor", "Momentum factor", FACTORS, korean="모멘텀 팩터",
        definition="Favors stocks whose prices and earnings expectations have been rising. "
                   "It rests on the observation that trends tend to persist for a while, "
                   "because investors react to news gradually and herd.",
        in_app="Built from price momentum (1/3/6/12-month returns), the 1-month EPS "
               "estimate revision and the 3-month change in foreign ownership.",
        related=("price-momentum", "eps-revision", "foreign-ownership-change",
                 "trailing-return", "trend-agreement"),
    ),
    Entry(
        "quality-factor", "Quality factor", FACTORS, korean="퀄리티 팩터",
        definition="Favors financially sound, consistently profitable companies. "
                   "High-quality stocks tend to recover from corrections and keep their "
                   "leadership; weak-fundamental stocks that spike often give the gains "
                   "back.",
        in_app="Built from operating margin, ROE, ROIC and debt-to-equity (lower is better).",
        related=("operating-margin", "roe", "roic", "debt-to-equity", "speculative-risk"),
    ),
    Entry(
        "percentile-rank", "Percentile rank", FACTORS, aliases=("percentile", "pctl"),
        korean="백분위 순위",
        definition="A stock's position within a group, from 0 to 100: the percentage of "
                   "the group it ranks at or above. 100 means best in the group; 50 is "
                   "the middle.",
        formula=r"\text{Percentile} = \frac{\text{rank (1 = worst)}}{N} \times 100",
        example="In a universe of 300 stocks, the stock with the 270th-lowest ROE has an "
                "ROE percentile of 270 / 300 × 100 = 90.",
        interpret="Percentiles are relative: a 90 means 'better than 90% of this "
                  "universe', not 'good' in absolute terms. They are robust to outliers, "
                  "which is why the app ranks rather than averaging raw values.",
        in_app="Every metric is converted to a percentile within the ranking scope "
               "(the market or, in sector mode, the sector). Lower-is-better metrics "
               "(debt-to-equity) are flipped so 100 is always best.",
        related=("factor-score", "rank-within-sector", "z-score"),
    ),
    Entry(
        "factor-score", "Factor score", FACTORS,
        aliases=("group score", "Value score", "Growth score", "Momentum score",
                 "Quality score"),
        korean="팩터 점수",
        definition="A stock's 0–100 score on one factor group, summarizing all of that "
                   "group's metrics.",
        formula=r"\text{Factor score} = \text{PercentileRank}\Big(\tfrac{1}{k}"
                r"\sum_{i=1}^{k}\text{Percentile}(\text{metric}_i)\Big)",
        example="A stock at the 80th, 60th, 90th and 70th percentiles on the four Value "
                "metrics averages 75; that average is then ranked against every other "
                "stock's average to give its Value score.",
        in_app="Needs at least half of the group's metrics (the coverage rule); "
               "otherwise the score is blank.",
        related=("percentile-rank", "composite-score", "coverage-rule", "factor"),
    ),
    Entry(
        "composite-score", "Composite score", FACTORS, aliases=("composite", "overall score"),
        korean="종합 점수",
        definition="The overall 0–100 score: the average of the four factor scores. Used "
                   "to sort the leaderboard and to give each stock its rank.",
        formula=r"\text{Composite} = \frac{\text{Value} + \text{Growth} + \text{Momentum}"
                r" + \text{Quality}}{4}",
        example="Scores of Value 80, Growth 60, Momentum 90, Quality 70 give a composite "
                "of 75.",
        interpret="A high composite can hide a weak factor — check the four scores, or "
                  "the all-round rule, which requires every factor to be strong.",
        in_app="Averages whichever factor scores exist. 'Rank' (#) is the composite rank "
               "within the stock's market, or within its sector in sector mode.",
        related=("factor-score", "all-round-leader", "market-leader"),
    ),
    Entry(
        "coverage-rule", "Coverage rule", FACTORS, aliases=("missing data", "minimum coverage"),
        korean="데이터 커버리지 규칙",
        definition="The app's rule for missing data: a factor score is computed only if "
                   "at least 50% of that factor's metrics are available for the stock.",
        example="If only 1 of the 4 Quality metrics is available, the Quality score is "
                "blank instead of resting on a single number.",
        in_app="A missing metric drops out of its own ranking only. A stock with any "
               "blank factor cannot be an all-round leader (it can still be a standout "
               "in the factors it has). Set by LEADER_MIN_COVERAGE in config.py.",
        related=("factor-score", "all-round-leader", "proxy"),
    ),
    Entry(
        "rank-within-sector", "Rank within sector", FACTORS,
        aliases=("sector-neutral ranking", "sector neutral", "sector-relative"),
        korean="섹터 내 순위 (섹터 중립)",
        definition="Ranking each stock only against companies in the same sector, instead "
                   "of the whole market. This removes structural differences between "
                   "industries from the comparison.",
        example="Banks always look cheap on book-to-market and highly levered on "
                "debt-to-equity. Ranked market-wide they crowd the Value list and sink in "
                "Quality; ranked within Financials they compete only with other banks.",
        in_app="Market Leaders sidebar → Rank within: Sector. Sectors with fewer than 5 "
               "companies (MIN_SECTOR_SIZE) and unclassified stocks are ranked against "
               "the whole market; the 'Ranked vs' column shows which applied.",
        related=("sector", "percentile-rank", "universe"),
    ),
    Entry(
        "universe", "Universe", FACTORS, aliases=("peer universe", "peers", "screening universe"),
        korean="유니버스 (비교 대상군)",
        definition="The set of stocks being compared. Every percentile and rank is relative "
                   "to the universe, so the same stock can score differently in a "
                   "different universe.",
        in_app="KOSPI and NASDAQ universes are the 300 largest companies by market cap in "
               "each market (PEER_TOP_N), plus — for NASDAQ — every Nasdaq-100 member, "
               "plus your holdings for KOSPI. 'Nasdaq-100' ranks only the index's 100 "
               "companies.",
        related=("peer-snapshot", "nasdaq-100", "market-cap", "rank-within-sector"),
    ),
    Entry(
        "z-score", "Z-score", FACTORS, aliases=("standard score", "Mom z", "Carry z"),
        korean="Z 점수 (표준점수)",
        definition="How many standard deviations a value sits above or below the group "
                   "average.",
        formula=r"z = \frac{x - \bar{x}}{\sigma}",
        example="If holdings' momentum averages 5% with a standard deviation of 10%, a "
                "holding at 25% has z = (25 − 5) / 10 = 2.0.",
        interpret="0 is average; ±1 is one standard deviation away; beyond ±2 is unusual.",
        in_app="The Portfolio Dashboard's factor heatmap shows momentum and carry as "
               "z-scores across your holdings.",
        related=("percentile-rank", "portfolio-momentum"),
    ),

    # =====================================================================
    # Value metrics
    # =====================================================================
    Entry(
        "pe", "P/E ratio", VALUE,
        aliases=("PER", "P/E", "PE", "price-to-earnings", "price earnings ratio"),
        korean="주가수익비율 (PER)",
        definition="The price investors pay for each unit of a company's annual earnings.",
        measures="How expensive a stock is relative to its profits — equivalently, how "
                 "many years of current earnings it would take to 'earn back' the price.",
        formula=r"\text{P/E} = \frac{\text{Share price}}{\text{EPS}}"
                r" = \frac{\text{Market capitalization}}{\text{Net income}}",
        example="Share price ₩50,000 and EPS ₩5,000 → P/E = 50,000 / 5,000 = 10×. "
                "A ₩100 trillion company earning ₩8 trillion a year has P/E = 12.5×.",
        interpret="Lower = cheaper per unit of earnings. A high P/E can mean expected "
                  "growth or overvaluation; a very low one can mean risk or a temporary "
                  "earnings spike. P/E is meaningless when earnings are negative, and "
                  "comparisons work best within the same industry.",
        in_app="Shown in the Value columns for readability. The model ranks its inverse, "
               "earnings yield, which stays meaningful for loss-makers. P/E shows "
               "'None' when earnings are ≤ 0.",
        related=("earnings-yield", "eps", "net-income", "market-cap", "pb", "value-factor"),
    ),
    Entry(
        "earnings-yield", "Earnings yield", VALUE, aliases=("E/P", "EY"),
        korean="이익수익률 (E/P)",
        definition="Annual earnings as a percentage of the company's market value — the "
                   "inverse of P/E.",
        measures="The 'return' the company's current profits represent on its price, "
                 "directly comparable with a bond yield.",
        formula=r"\text{Earnings yield} = \frac{\text{EPS}}{\text{Share price}}"
                r" = \frac{\text{Net income}}{\text{Market cap}} = \frac{1}{\text{P/E}}",
        example="P/E of 12.5× → earnings yield = 1 / 12.5 = 8%. If government bonds "
                "yield 5%, the stock's 8% looks relatively attractive, all else equal.",
        interpret="Higher = cheaper. Unlike P/E it handles losses smoothly: a loss-maker "
                  "simply has a negative yield and ranks last.",
        in_app="Value input, higher is better. Free data: net income to common "
               "shareholders ÷ market cap, with statements converted to the trading "
               "currency for foreign listings (ADRs).",
        related=("pe", "net-income", "market-cap", "value-factor", "adr-currency"),
    ),
    Entry(
        "pb", "P/B ratio", VALUE,
        aliases=("PBR", "P/B", "PB", "price-to-book", "price to book value"),
        korean="주가순자산비율 (PBR)",
        definition="The price investors pay for each unit of a company's net assets "
                   "(book value) on its balance sheet.",
        measures="How the market values the company relative to the accounting value of "
                 "its equity — what shareholders would notionally get if assets were "
                 "sold and debts repaid.",
        formula=r"\text{P/B} = \frac{\text{Share price}}{\text{BPS}}"
                r" = \frac{\text{Market capitalization}}{\text{Shareholders' equity}}",
        example="Share price ₩40,000 and book value per share ₩50,000 → P/B = 0.8×: "
                "the stock trades below its net assets.",
        interpret="Below 1× = priced under book value (often seen as downside protection, "
                  "or a sign the market doubts the assets or returns). High P/B usually "
                  "goes with high ROE (P/B ≈ ROE × P/E). Less useful for asset-light "
                  "firms whose value is intangible.",
        in_app="Shown in the Value columns for readability. The model ranks its inverse, "
               "book-to-market. P/B shows 'None' for negative equity.",
        related=("book-to-market", "book-value", "roe", "pe", "value-factor"),
    ),
    Entry(
        "book-to-market", "Book-to-market ratio", VALUE, aliases=("B/P", "B/M", "BM"),
        korean="장부가 대비 시가 (B/P)",
        definition="Book value (net assets) as a multiple of market value — the inverse "
                   "of P/B.",
        measures="How much accounting net worth stands behind each unit of market value.",
        formula=r"\text{B/M} = \frac{\text{Shareholders' equity}}{\text{Market cap}}"
                r" = \frac{1}{\text{P/B}}",
        example="P/B of 0.8× → B/M = 1 / 0.8 = 1.25: ₩1.25 of book value per ₩1 of "
                "market value.",
        interpret="Higher = cheaper relative to net assets. Negative equity gives a "
                  "negative B/M and ranks last.",
        in_app="Value input, higher is better. Free data: latest stockholders' equity ÷ "
               "market cap.",
        related=("pb", "book-value", "market-cap", "value-factor"),
    ),
    Entry(
        "dividend-yield", "Dividend yield", VALUE, aliases=("DY", "yield"),
        korean="배당수익률",
        definition="Annual dividends per share as a percentage of the share price.",
        measures="The cash return shareholders receive from dividends at today's price.",
        formula=r"\text{Dividend yield} = \frac{\text{Annual dividend per share}}"
                r"{\text{Share price}}",
        example="Annual dividend ₩1,500 on a ₩50,000 share → 1,500 / 50,000 = 3.0%.",
        interpret="Higher = more cash returned. A very high yield can signal a falling "
                  "price or an unsustainable payout. In Korea, companies raising "
                  "dividends and cancelling bought-back shares have been re-rated upward.",
        in_app="Value input, higher is better. Free data: annual dividend rate ÷ price; "
               "companies that pay no dividend count as 0%.",
        related=("payout-ratio", "value-factor", "pe"),
    ),
    Entry(
        "cash-flow-yield", "Cash-flow yield", VALUE, aliases=("CF yield", "CF/P"),
        korean="현금흐름수익률",
        definition="Operating cash flow as a percentage of the company's market value.",
        measures="How much cash the business actually generates relative to its price — "
                 "harder to flatter with accounting choices than earnings.",
        formula=r"\text{CF yield} = \frac{\text{Operating cash flow}}{\text{Market cap}}",
        example="Operating cash flow ₩9 trillion on a ₩100 trillion market cap → 9%.",
        interpret="Higher = more cash per unit of price. Especially telling in "
                  "capital-intensive industries that need cash to reinvest.",
        in_app="Value input, higher is better. Free data: trailing operating cash flow ÷ "
               "market cap.",
        related=("earnings-yield", "market-cap", "value-factor"),
    ),

    # =====================================================================
    # Growth metrics
    # =====================================================================
    Entry(
        "revenue-revision", "Forward revenue revision", GROWTH,
        aliases=("revenue growth", "Revenue (fwd)", "Fwd-12M revenue revision"),
        korean="매출 추정치 상향 (12개월 선행)",
        definition="How much analysts have raised (or cut) their consensus forecast of a "
                   "company's revenue for the next 12 months.",
        measures="Whether demand for the company's products is improving faster than "
                 "expected. Profit can grow by cutting costs; revenue growth needs more "
                 "sales.",
        formula=r"\text{Revision} = \frac{\text{Fwd-12M revenue estimate}_{\,now}}"
                r"{\text{Fwd-12M revenue estimate}_{\,then}} - 1",
        example="Consensus moved from ₩100 trillion to ₩104 trillion → +4% revision.",
        interpret="Positive and rising = expectations improving.",
        in_app="Growth input, higher is better. Free data has no revision history, so "
               "the app uses a proxy: the consensus revenue growth estimate for next "
               "fiscal year. Supply real revisions via the fundamentals override file.",
        related=("consensus", "forward-12m", "op-margin-change", "operating-leverage",
                 "proxy", "revenue"),
    ),
    Entry(
        "op-margin-change", "Operating-margin change", GROWTH,
        aliases=("op-margin change", "Op-margin Δ", "margin improvement"),
        korean="영업이익률 개선폭",
        definition="The expected change in a company's operating margin, in percentage "
                   "points.",
        measures="Whether each unit of sales is becoming more profitable — through scale "
                 "economies, pricing power or a richer product mix. Margin turns often "
                 "show up before revenue does.",
        formula=r"\Delta\,\text{Op. margin} = \text{Op. margin}_{\,next}"
                r" - \text{Op. margin}_{\,current}",
        example="Margin forecast to go from 12.0% to 13.5% → +1.5 pp.",
        interpret="Positive = improving profitability. Together with rising revenue it "
                  "signals operating leverage.",
        in_app="Growth input, higher is better, shown in pp. Free-data proxy: the change "
               "in operating margin between the last two fiscal years (trailing).",
        related=("operating-margin", "operating-leverage", "revenue-revision",
                 "percentage-point", "proxy"),
    ),
    Entry(
        "eps-growth", "Forward EPS growth", GROWTH,
        aliases=("EPS growth", "EPS growth (fwd)", "Fwd-12M EPS growth"),
        korean="선행 EPS 성장률",
        definition="The expected growth in earnings per share over the next 12 months.",
        measures="How fast the profit attributable to each share is expected to grow — "
                 "the part of growth that actually reaches shareholders.",
        formula=r"\text{EPS growth} = \frac{\text{Forward-12M EPS}}{\text{Trailing-12M EPS}} - 1",
        example="Trailing EPS ₩4,000 and consensus forward EPS ₩5,000 → +25%.",
        interpret="Higher = faster expected per-share profit growth. Meaningless when "
                  "current EPS is zero or negative.",
        in_app="Growth input, higher is better. Free data: Yahoo's forward EPS ÷ trailing "
               "EPS − 1; 'None' when trailing EPS ≤ 0.",
        related=("eps", "forward-12m", "consensus", "eps-revision", "growth-factor"),
    ),
    Entry(
        "long-term-growth", "Long-term (sustainable) growth", GROWTH,
        aliases=("LT growth", "sustainable growth rate", "SGR"),
        korean="장기 (지속가능) 성장률",
        definition="The growth rate a company can sustain from its own profits: how much "
                   "it reinvests, times how well those reinvestments earn.",
        measures="Whether growth is structural rather than a one-year bump.",
        formula=r"g = \text{ROE} \times (1 - \text{Payout ratio})",
        example="ROE 15% and 30% of profits paid as dividends → g = 15% × 0.70 = 10.5%.",
        interpret="Higher = more self-funded growth capacity. A high-ROE company that "
                  "retains most of its profit can compound shareholder value.",
        in_app="Growth input, higher is better. Derived automatically from ROE and payout "
               "ratio when not supplied.",
        related=("roe", "payout-ratio", "growth-factor"),
    ),
    Entry(
        "payout-ratio", "Payout ratio", GROWTH, korean="배당성향",
        definition="The share of net income paid out to shareholders as dividends.",
        formula=r"\text{Payout ratio} = \frac{\text{Dividends}}{\text{Net income}}",
        example="₩3 trillion of dividends from ₩10 trillion of net income → 30%.",
        interpret="Its complement (1 − payout) is the retention ratio — the share "
                  "reinvested in the business.",
        in_app="Not scored directly; used to compute long-term growth.",
        related=("long-term-growth", "dividend-yield", "net-income"),
    ),
    Entry(
        "operating-leverage", "Operating leverage", GROWTH, aliases=("operating leverage tag",),
        korean="영업 레버리지",
        definition="When revenue grows and the operating margin improves at the same time, "
                   "profits grow faster than sales because fixed costs are spread over more "
                   "revenue.",
        interpret="The point where a leading stock's price starts to accelerate often "
                  "coincides with this phase, as the market builds strong expectations.",
        in_app="Tag shown when both the forward revenue revision and the operating-margin "
               "change are positive.",
        related=("revenue-revision", "op-margin-change", "operating-margin", "tags"),
    ),

    # =====================================================================
    # Momentum metrics
    # =====================================================================
    Entry(
        "price-momentum", "Price momentum", MOMENTUM, aliases=("price momentum score",),
        korean="가격 모멘텀",
        definition="A score of how strongly and consistently a stock's price has been "
                   "rising, combining short- and long-term returns.",
        measures="1–3 month returns capture the market's current attention; 6–12 month "
                 "returns show whether that interest is a sustained trend. When both point "
                 "the same way the signal is more reliable.",
        formula=r"\text{Score} = 0.5 + (\overline{\text{rank}} - 0.5) \times \text{agreement}",
        example="A stock ranking at the 90th percentile on average across horizons, with "
                "all four horizons up (agreement 1.0), scores 0.9. With two up and two "
                "down (agreement 0) it is pulled to a neutral 0.5.",
        interpret="Higher = stronger, more consistent uptrend relative to peers.",
        in_app="Momentum input. Average cross-sectional rank of the 1/3/6/12-month "
               "returns (21/63/126/252 trading days), shrunk toward neutral by trend "
               "agreement. Computed from prices, including the latest quote on Company "
               "Analysis.",
        related=("trailing-return", "trend-agreement", "momentum-factor", "tsmom"),
    ),
    Entry(
        "trailing-return", "Trailing return", MOMENTUM,
        aliases=("1M", "3M", "6M", "12M", "return"),
        korean="과거 수익률",
        definition="The percentage price change over a past period ending today.",
        formula=r"r_{h} = \frac{P_{t}}{P_{t-h}} - 1",
        example="A stock at ₩55,000 that traded at ₩50,000 63 trading days ago has a "
                "3-month return of +10%.",
        in_app="Horizons: 1M = 21, 3M = 63, 6M = 126, 12M = 252 trading days, using "
               "adjusted closes. Shown in the Momentum columns.",
        related=("price-momentum", "trading-day", "ytd"),
    ),
    Entry(
        "trend-agreement", "Trend agreement", MOMENTUM, korean="추세 일치도",
        definition="How consistently a stock's 1/3/6/12-month returns point the same way.",
        formula=r"\text{Agreement} = \frac{|\#\text{up} - \#\text{down}|}{\#\text{horizons}}",
        example="All four horizons up → 1.0. Three up, one down → 0.5. Two and two → 0.",
        in_app="Scales the price momentum score toward neutral when horizons disagree.",
        related=("price-momentum", "trailing-return"),
    ),
    Entry(
        "eps-revision", "EPS revision (1M)", MOMENTUM,
        aliases=("earnings momentum", "EPS rev. 1M", "earnings revision"),
        korean="EPS 추정치 변화 (1개월)",
        definition="How much analysts' consensus EPS forecast has changed over the past "
                   "month.",
        measures="Earnings momentum: a chain of positive surprises — the company beats "
                 "expectations, analysts raise estimates, and it beats again.",
        formula=r"\text{Revision} = \frac{\text{EPS estimate}_{\,now} - \text{EPS estimate}"
                r"_{\,30d\ ago}}{|\text{EPS estimate}_{\,30d\ ago}|}",
        example="Forward EPS estimate raised from ₩5,000 to ₩5,200 in a month → +4%.",
        interpret="Positive = analysts becoming more optimistic.",
        in_app="Momentum input, higher is better. Free data: Yahoo's EPS trend for next "
               "fiscal year (current fiscal year as fallback), now vs 30 days ago.",
        related=("consensus", "eps", "eps-growth", "momentum-factor"),
    ),
    Entry(
        "foreign-ownership-change", "Foreign ownership change (3M)", MOMENTUM,
        aliases=("foreign investor buying", "Foreign Δ 3M"),
        korean="외국인 지분율 변화 (3개월)",
        definition="The change in the share of a company's stock held by foreign "
                   "investors over three months, in percentage points.",
        measures="Recognition by global institutional capital — particularly influential "
                 "in the Korean market.",
        formula=r"\Delta = \text{Foreign ownership}_{\,now} - \text{Foreign ownership}"
                r"_{\,3M\ ago}",
        example="Foreign ownership rising from 52.0% to 53.4% → +1.4 pp.",
        in_app="Momentum input, higher is better. Not available from free sources — the "
               "Momentum score is then built from its other two inputs (coverage rule). "
               "Supply it via the fundamentals override file.",
        related=("momentum-factor", "coverage-rule", "fundamentals-override",
                 "percentage-point"),
    ),

    # =====================================================================
    # Quality metrics
    # =====================================================================
    Entry(
        "operating-margin", "Operating margin", QUALITY,
        aliases=("operating profit margin", "Op. margin", "OPM"),
        korean="영업이익률",
        definition="Operating profit as a percentage of revenue: how much of each unit of "
                   "sales is left after running the business, before interest and taxes.",
        measures="Pricing power and cost efficiency — companies that can pass rising costs "
                 "on to customers keep high margins.",
        formula=r"\text{Operating margin} = \frac{\text{Operating profit}}{\text{Revenue}}",
        example="Operating profit ₩12 trillion on revenue ₩80 trillion → 15%.",
        interpret="Higher = more profitable operations. Compare within an industry; "
                  "retailers and chipmakers have very different normal margins.",
        in_app="Quality input, higher is better. Definition is forward-12M; free-data "
               "proxy: trailing-12M operating margin.",
        related=("op-margin-change", "operating-profit", "revenue", "quality-factor",
                 "proxy"),
    ),
    Entry(
        "roe", "Return on equity (ROE)", QUALITY, aliases=("ROE",),
        korean="자기자본이익률 (ROE)",
        definition="Net income as a percentage of shareholders' equity: the annual profit "
                   "generated on the capital shareholders have invested.",
        measures="How effectively the company turns shareholders' money into profit.",
        formula=r"\text{ROE} = \frac{\text{Net income}}{\text{Shareholders' equity}}",
        example="Net income ₩15 trillion on equity ₩100 trillion → ROE 15%.",
        interpret="Higher is better, and sustained high ROE with reinvestment compounds "
                  "value. Caveat: ROE can be inflated by debt — shrinking equity and "
                  "borrowing more raises ROE with no change in earnings. Check ROIC and "
                  "debt-to-equity alongside it.",
        in_app="Quality input, higher is better; also feeds long-term growth.",
        related=("roic", "debt-to-equity", "net-income", "book-value", "long-term-growth",
                 "pb"),
    ),
    Entry(
        "roic", "Return on invested capital (ROIC)", QUALITY, aliases=("ROIC",),
        korean="투하자본이익률 (ROIC)",
        definition="After-tax operating profit as a percentage of all capital invested in "
                   "the business — from both shareholders and lenders.",
        measures="Profitability of the business itself, independent of how it is financed. "
                 "Unlike ROE it can't be boosted by swapping equity for debt.",
        formula=r"\text{ROIC} = \frac{\text{EBIT} \times (1 - \text{tax rate})}"
                r"{\text{Invested capital}}",
        example="EBIT ₩20 trillion, tax rate 25%, invested capital ₩120 trillion → "
                "20 × 0.75 / 120 = 12.5%.",
        interpret="Higher is better. ROIC above the company's cost of capital means growth "
                  "creates value.",
        in_app="Quality input, higher is better. Free data: latest fiscal-year EBIT × "
               "(1 − effective tax rate; 25% if not reported) ÷ invested capital.",
        related=("roe", "ebit", "invested-capital", "quality-factor"),
    ),
    Entry(
        "debt-to-equity", "Debt-to-equity ratio", QUALITY,
        aliases=("D/E", "Debt/Equity", "leverage", "financial soundness"),
        korean="부채 대 자기자본 비율 (D/E)",
        definition="A company's total borrowings relative to its shareholders' equity.",
        measures="Financial soundness — how much the company relies on debt. Strong "
                 "balance sheets survive rate spikes and credit stress and can buy "
                 "assets cheaply when weaker rivals are forced to sell or dilute.",
        formula=r"\text{D/E} = \frac{\text{Total debt}}{\text{Shareholders' equity}}",
        example="Debt ₩30 trillion and equity ₩60 trillion → D/E = 0.5×.",
        interpret="Lower = sounder. Note: the commonly quoted Korean 부채비율 uses total "
                  "liabilities (including payables), not just borrowings, so it reads "
                  "higher than D/E.",
        in_app="Quality input, lower is better (ranking it in reverse is equivalent to "
               "scoring its inverse). Free data: total debt ÷ stockholders' equity. "
               "Negative equity ranks worst and displays as 'None'.",
        related=("roe", "book-value", "quality-factor", "negative-equity"),
    ),

    # =====================================================================
    # Financial statement basics
    # =====================================================================
    Entry(
        "eps", "Earnings per share (EPS)", BASICS, aliases=("EPS",),
        korean="주당순이익 (EPS)",
        definition="Net income divided by the number of shares outstanding: the profit "
                   "attributable to each share.",
        formula=r"\text{EPS} = \frac{\text{Net income}}{\text{Shares outstanding}}",
        example="₩10 trillion net income and 2 billion shares → EPS ₩5,000.",
        related=("pe", "eps-growth", "eps-revision", "net-income"),
    ),
    Entry(
        "book-value", "Book value (BPS)", BASICS,
        aliases=("BPS", "shareholders' equity", "net assets", "equity"),
        korean="순자산 / 주당순자산 (BPS)",
        definition="Shareholders' equity on the balance sheet — total assets minus total "
                   "liabilities. Per share, it is book value per share (BPS).",
        formula=r"\text{BPS} = \frac{\text{Total assets} - \text{Total liabilities}}"
                r"{\text{Shares outstanding}}",
        related=("pb", "book-to-market", "roe", "negative-equity"),
    ),
    Entry(
        "net-income", "Net income", BASICS, aliases=("net profit", "earnings"),
        korean="순이익 (당기순이익)",
        definition="Profit after all expenses, interest and taxes — the bottom line of the "
                   "income statement.",
        related=("eps", "earnings-yield", "roe", "operating-profit"),
    ),
    Entry(
        "revenue", "Revenue", BASICS, aliases=("sales", "top line"), korean="매출액",
        definition="Total income from selling goods and services before any costs — the "
                   "top line of the income statement.",
        related=("revenue-revision", "operating-margin"),
    ),
    Entry(
        "operating-profit", "Operating profit", BASICS,
        aliases=("operating income",), korean="영업이익",
        definition="Revenue minus the costs of running the business (cost of sales, "
                   "selling and administrative expenses), before interest and taxes.",
        related=("operating-margin", "ebit", "net-income"),
    ),
    Entry(
        "ebit", "EBIT", BASICS, aliases=("earnings before interest and taxes",),
        korean="이자 및 법인세 차감 전 이익 (EBIT)",
        definition="Earnings before interest and taxes: operating profit plus or minus "
                   "non-operating items, before financing costs and tax. Close to operating "
                   "profit for most companies.",
        related=("roic", "operating-profit"),
    ),
    Entry(
        "invested-capital", "Invested capital", BASICS, korean="투하자본",
        definition="The total capital put into the business by shareholders and lenders — "
                   "roughly equity plus debt, less excess cash.",
        related=("roic", "debt-to-equity", "book-value"),
    ),
    Entry(
        "market-cap", "Market capitalization", BASICS, aliases=("market cap", "marcap"),
        korean="시가총액",
        definition="The stock market's total value of a company: share price times shares "
                   "outstanding.",
        formula=r"\text{Market cap} = \text{Share price} \times \text{Shares outstanding}",
        example="₩60,000 × 6 billion shares = ₩360 trillion.",
        in_app="Defines each market's universe (the 300 largest) and is the denominator "
               "of the value yields.",
        related=("universe", "earnings-yield", "pe", "pb"),
    ),
    Entry(
        "negative-equity", "Negative equity", BASICS, aliases=("capital impairment",),
        korean="자본잠식",
        definition="When a company's liabilities exceed its assets, so shareholders' "
                   "equity is below zero.",
        interpret="Ratios divided by equity (P/B, D/E, ROE) become misleading: a negative "
                  "D/E would wrongly look 'low'.",
        in_app="The app ranks negative-equity companies worst on debt-to-equity and shows "
               "their P/B and D/E as 'None'.",
        related=("debt-to-equity", "book-value", "pb"),
    ),
    Entry(
        "consensus", "Consensus estimate", BASICS,
        aliases=("analyst consensus", "estimate"), korean="컨센서스 (시장 추정치)",
        definition="The average of analysts' forecasts for a company's revenue, earnings or "
                   "other figures.",
        interpret="Changes in consensus (revisions) often move prices more than the level "
                  "itself.",
        related=("forward-12m", "eps-revision", "revenue-revision"),
    ),
    Entry(
        "forward-12m", "Forward 12-month (Fwd-12M)", BASICS,
        aliases=("forward", "fwd", "NTM", "next twelve months", "12M forward"),
        korean="12개월 선행",
        definition="A figure covering the next 12 months, based on analyst estimates — as "
                   "opposed to trailing figures, which cover the past 12 months (TTM).",
        related=("consensus", "eps-growth", "revenue-revision", "operating-margin"),
    ),

    # =====================================================================
    # Market leaders
    # =====================================================================
    Entry(
        "market-leader", "Market leader", LEADERS, aliases=("leader", "leading stock"),
        korean="주도주",
        definition="A stock that ranks highly across all four factors, or achieves an "
                   "exceptionally strong score in at least one of them.",
        in_app="Two rules: all-round leader and standout leader. Thresholds are sidebar "
               "sliders on Market Leaders and apply on every page.",
        related=("all-round-leader", "standout-leader", "composite-score", "leader-map"),
    ),
    Entry(
        "all-round-leader", "All-round leader", LEADERS, korean="전방위 주도주",
        definition="A stock whose every factor score is at or above a threshold "
                   "percentile — strong on Value, Growth, Momentum and Quality at once.",
        formula=r"\min(\text{Value}, \text{Growth}, \text{Momentum}, \text{Quality})"
                r" \geq \text{threshold}",
        example="With the default 60th-percentile threshold, scores of 72 / 65 / 88 / 61 "
                "qualify; 72 / 65 / 88 / 55 do not.",
        in_app="Default threshold 60 (LEADER_ALL_ROUND_PCT). A blank factor disqualifies "
               "the stock.",
        related=("market-leader", "standout-leader", "breadth-peak", "coverage-rule"),
    ),
    Entry(
        "standout-leader", "Standout leader", LEADERS, korean="특정 팩터 주도주",
        definition="A stock with an exceptionally high score on at least one factor, "
                   "whatever its other scores.",
        formula=r"\max(\text{Value}, \text{Growth}, \text{Momentum}, \text{Quality})"
                r" \geq \text{threshold}",
        example="With the default 95th-percentile threshold, a stock scoring 97 on "
                "Momentum is a standout leader 'in Momentum' even if its Value score is 20.",
        interpret="Check the tags: a value-only standout can be a value trap; a "
                  "momentum-only standout on weak quality can be speculative.",
        in_app="Default threshold 95 (LEADER_STANDOUT_PCT). The 'Standout in' column "
               "names the factor(s).",
        related=("market-leader", "all-round-leader", "value-trap", "speculative-risk"),
    ),
    Entry(
        "breadth-peak", "Breadth and peak", LEADERS,
        aliases=("breadth", "peak", "weakest factor", "strongest factor"),
        korean="최저/최고 팩터 점수",
        definition="Breadth is a stock's weakest factor score; peak is its strongest. "
                   "Breadth tests the all-round rule, peak tests the standout rule.",
        related=("leader-map", "all-round-leader", "standout-leader"),
    ),
    Entry(
        "leader-map", "Leader map", LEADERS, korean="주도주 맵",
        definition="A scatter chart with each stock's weakest factor score on the x-axis "
                   "and its strongest on the y-axis.",
        interpret="Points right of the dotted line are all-round leaders; points above the "
                  "dashed line are standout leaders. Ringed points are your holdings.",
        in_app="Market Leaders → Leader map tab.",
        related=("breadth-peak", "market-leader"),
    ),
    Entry(
        "tags", "Tags", LEADERS, aliases=("caveat tags",), korean="태그",
        definition="Context flags added to a stock's scores: Operating leverage, Value-trap "
                   "risk and Speculative risk.",
        related=("operating-leverage", "value-trap", "speculative-risk"),
    ),
    Entry(
        "value-trap", "Value trap", LEADERS, aliases=("value-trap risk",),
        korean="가치 함정",
        definition="A stock that looks cheap but stays cheap — or gets cheaper — because "
                   "nothing changes the market's view of it. Common in long stretches of "
                   "low rates and growth-stock dominance.",
        in_app="Tag 'Value-trap risk': Value score ≥ 70 while Growth and Momentum are both "
               "below 40 — cheap with no catalyst.",
        related=("value-factor", "tags", "standout-leader"),
    ),
    Entry(
        "speculative-risk", "Speculative risk", LEADERS, aliases=("theme stock",),
        korean="투기적 위험 (테마주)",
        definition="Strong price momentum that isn't backed by solid fundamentals — the "
                   "pattern of theme-driven stocks that surge and then give the gains back.",
        in_app="Tag 'Speculative risk': Momentum score ≥ 70 while Quality is below 30.",
        related=("quality-factor", "momentum-factor", "tags"),
    ),

    # =====================================================================
    # Portfolio
    # =====================================================================
    Entry(
        "market-value", "Market value (position)", PORTFOLIO, korean="평가금액",
        definition="What a holding is worth at the current price.",
        formula=r"\text{Market value} = \text{Quantity} \times \text{Current price}",
        example="120 shares at ₩24,750 = ₩2,970,000.",
        related=("unrealized-pl", "portfolio-weight"),
    ),
    Entry(
        "average-price", "Average purchase price", PORTFOLIO,
        aliases=("avg price", "average cost"), korean="평균매입가",
        definition="The average price paid per share across all purchases of a holding.",
        formula=r"\text{Avg price} = \frac{\text{Total purchase amount}}{\text{Quantity}}",
        related=("unrealized-pl",),
    ),
    Entry(
        "unrealized-pl", "Unrealized P/L", PORTFOLIO,
        aliases=("unrealized profit", "P/L", "평가손익"), korean="평가손익",
        definition="The gain or loss on a holding you still own, measured at today's price.",
        formula=r"\text{P/L} = (\text{Current price} - \text{Avg price}) \times \text{Quantity}"
                r",\quad \text{P/L\%} = \frac{\text{Current price}}{\text{Avg price}} - 1",
        example="Bought at ₩100,000, now ₩110,000, 10 shares → +₩100,000 (+10%).",
        in_app="Colored red for gains and blue for losses (Korean market convention), "
               "always with an explicit sign.",
        related=("average-price", "market-value"),
    ),
    Entry(
        "portfolio-weight", "Portfolio weight", PORTFOLIO, aliases=("weight",),
        korean="비중",
        definition="A holding's share of the portfolio's total market value.",
        formula=r"w_i = \frac{\text{Market value}_i}{\sum_j \text{Market value}_j}",
        related=("market-value", "portfolio-momentum", "in-market-leaders"),
    ),
    Entry(
        "portfolio-momentum", "Portfolio momentum", PORTFOLIO, korean="포트폴리오 모멘텀",
        definition="The value-weighted average trailing return of your holdings over the "
                   "selected window.",
        formula=r"\text{Portfolio momentum} = \sum_i w_i \, r_i",
        in_app="Portfolio Dashboard KPI; window chosen in the sidebar (20–252 days).",
        related=("portfolio-weight", "trailing-return", "z-score"),
    ),
    Entry(
        "in-market-leaders", "In market leaders", PORTFOLIO, korean="주도주 비중",
        definition="The share of your portfolio's market value held in stocks currently "
                   "classified as market leaders.",
        in_app="Portfolio Dashboard KPI, using the KOSPI peer snapshot and the "
               "thresholds set on Market Leaders.",
        related=("market-leader", "portfolio-weight"),
    ),
    Entry(
        "carry-proxy", "Carry proxy (dashboard)", PORTFOLIO, korean="캐리 대용치",
        definition="An annualized estimate of a holding's carry shown on the Portfolio "
                   "Dashboard.",
        in_app="Until a real carry source is wired in (strategies/carry.py), it is a "
               "placeholder: the gap between the 21- and 63-day moving averages of the "
               "price, annualized. It is not true carry.",
        related=("carry-strategy", "roll-yield"),
    ),

    # =====================================================================
    # Backtesting
    # =====================================================================
    Entry(
        "backtest", "Backtest", BACKTEST, korean="백테스트",
        definition="Simulating how a trading rule would have performed on historical data, "
                   "as if it had been followed at the time.",
        interpret="A good backtest avoids lookahead bias, charges realistic costs, and "
                  "compares against a benchmark. Past performance does not guarantee "
                  "future results.",
        in_app="Commodity ETF Backtester page; engine in backtest/engine.py.",
        related=("signal", "lookahead-bias", "transaction-cost", "buy-and-hold",
                 "equity-curve"),
    ),
    Entry(
        "signal", "Signal", BACKTEST, aliases=("trading signal",), korean="매매 신호",
        definition="A strategy's desired exposure to an asset each day: +1 fully long, "
                   "−1 fully short, 0 flat, with fractions for partial positions.",
        in_app="Strategies implement compute_signal(prices, params) → Series; the engine "
               "turns signals into positions.",
        related=("tsmom", "carry-strategy", "backtest"),
    ),
    Entry(
        "tsmom", "Time-series momentum (TSMOM)", BACKTEST,
        aliases=("TSMOM", "trend following"), korean="시계열 모멘텀",
        definition="A strategy that goes long an asset whose own price has risen over a "
                   "lookback period and short one that has fallen — trend following on "
                   "each asset independently.",
        formula=r"\text{signal}_t = \operatorname{sign}\!\Big(\frac{P_t}{P_{t-L}} - 1\Big)",
        example="With a 120-day lookback, an ETF up 8% over the last 120 trading days "
                "gets signal +1 (long).",
        in_app="Reference strategy in strategies/tsmom.py; capital split equally across "
               "the selected ETFs.",
        related=("lookback", "signal", "price-momentum", "carry-strategy"),
    ),
    Entry(
        "carry-strategy", "Carry strategy", BACKTEST, aliases=("carry",),
        korean="캐리 전략",
        definition="A strategy that favors assets that earn a positive return from simply "
                   "holding them — for commodity futures, mainly the roll yield.",
        in_app="Reference strategy in strategies/carry.py: ranks the ETFs by carry score, "
               "long the high-carry half and short the low-carry half, scaled to gross "
               "exposure 1. The real carry source is a TODO; until then it uses a "
               "placeholder proxy.",
        related=("roll-yield", "contango-backwardation", "carry-proxy", "tsmom"),
    ),
    Entry(
        "roll-yield", "Roll yield", BACKTEST, korean="롤 수익률",
        definition="The return from rolling a futures position from an expiring contract "
                   "to a later one. Positive when the later contract is cheaper "
                   "(backwardation), negative when it is dearer (contango).",
        formula=r"\text{Roll yield} = \Big(\frac{P_{\text{front}}}{P_{\text{next}}}\Big)"
                r"^{252/\text{days between expiries}} - 1",
        example="Front month $80, next month $78, 21 trading days apart → "
                "(80/78)^(252/21) − 1 ≈ +35% annualized.",
        related=("contango-backwardation", "carry-strategy"),
    ),
    Entry(
        "contango-backwardation", "Contango and backwardation", BACKTEST,
        aliases=("contango", "backwardation", "term structure"),
        korean="콘탱고 / 백워데이션",
        definition="The shape of a futures curve. Contango: later contracts cost more than "
                   "near ones (rolling loses money). Backwardation: later contracts are "
                   "cheaper (rolling earns money).",
        related=("roll-yield", "carry-strategy"),
    ),
    Entry(
        "lookback", "Lookback period", BACKTEST, aliases=("lookback",),
        korean="관찰 기간 (룩백)",
        definition="How many past trading days a signal looks at.",
        interpret="Short lookbacks react fast but trade more and whipsaw; long ones are "
                  "steadier but slower.",
        in_app="Backtester slider, 20–252 trading days.",
        related=("tsmom", "trading-day"),
    ),
    Entry(
        "rebalancing", "Rebalancing frequency", BACKTEST, aliases=("rebalance",),
        korean="리밸런싱 주기",
        definition="How often positions are reset to the strategy's target weights.",
        interpret="More frequent rebalancing tracks the signal closely but costs more in "
                  "transaction costs.",
        in_app="Daily, weekly or monthly; trades on the last trading day of each period.",
        related=("turnover", "transaction-cost"),
    ),
    Entry(
        "transaction-cost", "Transaction cost", BACKTEST,
        aliases=("trading cost", "bps cost", "commission"), korean="거래비용",
        definition="The cost of trading — commissions, taxes, bid-ask spread and market "
                   "impact — expressed as a fraction of the amount traded.",
        formula=r"\text{Cost}_t = \text{Turnover}_t \times \frac{\text{bps}}{10{,}000}",
        example="Turnover of 50% at 10 bps costs 0.5 × 0.001 = 0.05% of the portfolio "
                "that day.",
        in_app="Backtester input, one-way, charged on the day positions change.",
        related=("basis-point", "turnover", "rebalancing"),
    ),
    Entry(
        "turnover", "Turnover", BACKTEST, korean="회전율",
        definition="How much of the portfolio is traded, as the sum of absolute weight "
                   "changes.",
        formula=r"\text{Turnover}_t = \sum_i |w_{i,t} - w_{i,t-1}|",
        example="Moving from 100% in ETF A to 100% in ETF B is 200% turnover.",
        related=("transaction-cost", "rebalancing"),
    ),
    Entry(
        "lookahead-bias", "Lookahead bias", BACKTEST, korean="미래 정보 편향",
        definition="Using information in a backtest that wasn't available at the time of "
                   "the trade, which makes results look better than achievable.",
        in_app="Prevented by a one-day shift: a signal computed at day t's close is traded "
               "and earns returns from day t+1. A test checks this.",
        related=("backtest", "signal"),
    ),
    Entry(
        "equity-curve", "Equity curve", BACKTEST, aliases=("growth of 1",),
        korean="자산 곡선",
        definition="The value over time of ₩1 invested in a strategy, compounding its "
                   "daily net returns.",
        formula=r"E_t = \prod_{s \le t} (1 + r_s)",
        in_app="Backtester chart, against the buy-and-hold benchmark. The strategy's "
               "warm-up period (before its first position) is trimmed.",
        related=("buy-and-hold", "drawdown", "cagr"),
    ),
    Entry(
        "buy-and-hold", "Buy-and-hold benchmark", BACKTEST, korean="매수 후 보유 벤치마크",
        definition="The comparison portfolio for a backtest: buy the same assets at the "
                   "start and never trade.",
        in_app="Equal-weight across the selected ETFs, each bought at its first available "
               "price. KPI deltas show strategy minus benchmark.",
        related=("equity-curve", "benchmark", "backtest"),
    ),
    Entry(
        "cagr", "CAGR", BACKTEST, aliases=("compound annual growth rate", "annualized return"),
        korean="연평균 복리 수익률 (CAGR)",
        definition="The constant yearly return that would turn the starting value into "
                   "the ending value.",
        formula=r"\text{CAGR} = \Big(\frac{E_{end}}{E_{start}}\Big)^{1/\text{years}} - 1,"
                r"\quad \text{years} = \frac{\text{trading days}}{252}",
        example="₩1 growing to ₩1.61 over 5 years → 1.61^(1/5) − 1 ≈ 10% a year.",
        related=("equity-curve", "sharpe", "volatility"),
    ),
    Entry(
        "volatility", "Volatility", BACKTEST, aliases=("vol", "Vol 1Y", "standard deviation"),
        korean="변동성",
        definition="How much returns fluctuate, measured as the annualized standard "
                   "deviation of daily returns.",
        formula=r"\sigma_{annual} = \sigma_{daily} \times \sqrt{252}",
        example="Daily standard deviation 1% → about 15.9% annualized.",
        interpret="Lower = smoother ride. Volatility treats up and down moves alike.",
        in_app="Backtester KPI; 'Vol 1Y' on the Sector ETFs page uses the last year.",
        related=("sharpe", "max-drawdown"),
    ),
    Entry(
        "sharpe", "Sharpe ratio", BACKTEST, aliases=("Sharpe",), korean="샤프 지수",
        definition="Return per unit of risk: average excess return divided by volatility, "
                   "annualized.",
        formula=r"\text{Sharpe} = \frac{\overline{r - r_f}}{\sigma(r - r_f)} \times \sqrt{252}",
        example="Average daily excess return 0.04% and daily volatility 1% → "
                "0.04 / 1 × √252 ≈ 0.63.",
        interpret="Higher is better. Roughly: below 0.5 weak, 0.5–1 reasonable, above 1 "
                  "strong for a long-run strategy.",
        in_app="Backtester KPI, with a 0% risk-free rate.",
        related=("volatility", "cagr", "max-drawdown"),
    ),
    Entry(
        "drawdown", "Drawdown", BACKTEST, aliases=("underwater",), korean="낙폭",
        definition="How far a portfolio is below its previous peak at a given time.",
        formula=r"DD_t = \frac{E_t}{\max_{s \le t} E_s} - 1",
        in_app="The backtester's underwater chart plots this every day.",
        related=("max-drawdown", "equity-curve"),
    ),
    Entry(
        "max-drawdown", "Maximum drawdown (MDD)", BACKTEST,
        aliases=("MDD", "max DD", "Max DD 1Y"), korean="최대 낙폭 (MDD)",
        definition="The largest peak-to-trough fall over a period — the worst loss an "
                   "investor who bought at a high would have sat through.",
        formula=r"\text{MDD} = \min_t DD_t",
        example="Peak ₩1.40 falling to ₩1.05 → 1.05 / 1.40 − 1 = −25%.",
        interpret="Closer to 0 is better.",
        in_app="Backtester KPI; 'Max DD 1Y' on the Sector ETFs page uses the last year.",
        related=("drawdown", "volatility", "sharpe"),
    ),
    Entry(
        "hit-ratio", "Hit ratio", BACKTEST, aliases=("win rate",), korean="적중률 (승률)",
        definition="The share of days with a positive return.",
        formula=r"\text{Hit ratio} = \frac{\#\{\text{days with } r > 0\}}"
                r"{\#\{\text{days with a position}\}}",
        interpret="Above 50% means more up days than down; size of wins vs losses matters "
                  "as much.",
        in_app="Backtester KPI; days with no position are excluded.",
        related=("sharpe", "cagr"),
    ),

    # =====================================================================
    # Sectors & ETFs
    # =====================================================================
    Entry(
        "sector", "Sector", SECTORS, aliases=("industry group", "sector classification"),
        korean="섹터 (업종)",
        definition="A broad group of companies in similar businesses, e.g. Technology, "
                   "Financial Services, Healthcare.",
        in_app="Uses Yahoo Finance's 11-sector classification. Filter by it on Market "
               "Leaders, rank within it, or compare sectors on the Sectors tab.",
        related=("rank-within-sector", "sector-etf", "sector-overview"),
    ),
    Entry(
        "sector-overview", "Sector overview", SECTORS, aliases=("leader share",),
        korean="섹터 개요",
        definition="A per-sector summary: number of stocks, number and share of market "
                   "leaders, median factor scores and median returns.",
        in_app="Market Leaders → Sectors tab. Uses market-relative scores even in sector "
               "mode, so sectors can be compared (50 = market median).",
        related=("sector", "market-leader"),
    ),
    Entry(
        "sector-etf", "Sector ETF", SECTORS, korean="섹터 ETF",
        definition="An exchange-traded fund holding the stocks of one sector, letting you "
                   "track or trade the sector as a whole.",
        in_app="Sector ETFs page. US: Select Sector SPDRs (XLK, XLF, …) vs SPY. Korea: "
               "TIGER 200 sector series vs KODEX 200 — placeholder codes to verify.",
        related=("benchmark", "relative-strength", "sector"),
    ),
    Entry(
        "benchmark", "Benchmark", SECTORS, aliases=("SPY", "KODEX 200"), korean="벤치마크",
        definition="The reference an investment is measured against — usually the broad "
                   "market index.",
        in_app="SPY (S&P 500) for US sector ETFs; KODEX 200 (KOSPI 200) for Korean ones.",
        related=("relative-strength", "buy-and-hold"),
    ),
    Entry(
        "relative-strength", "Relative strength", SECTORS,
        aliases=("excess return", "RS"), korean="상대강도 (초과수익률)",
        definition="An asset's return minus its benchmark's return over the same period.",
        formula=r"\text{RS}_h = r_{\text{sector},h} - r_{\text{benchmark},h}",
        example="Sector +12%, benchmark +7% over 3 months → +5 pp relative strength.",
        interpret="Positive across several horizons = a persistent sector leader.",
        in_app="Sector ETFs heatmap at 1W, 1M, 3M, 6M, YTD and 1Y, in percentage points.",
        related=("benchmark", "percentage-point", "growth-of-100"),
    ),
    Entry(
        "growth-of-100", "Growth of 100", SECTORS, aliases=("rebased", "rebased performance"),
        korean="100 기준 환산 성과",
        definition="A price series rescaled so every line starts at 100, making assets "
                   "with different prices directly comparable.",
        formula=r"G_t = 100 \times \frac{P_t}{P_{start}}",
        example="A line ending at 118 has gained 18% since the start of the period.",
        in_app="Sector ETFs comparison chart.",
        related=("relative-strength", "equity-curve"),
    ),
    Entry(
        "ytd", "Year-to-date (YTD)", SECTORS, aliases=("YTD",), korean="연초 대비",
        definition="Performance from the last close of the previous year to today.",
        formula=r"r_{YTD} = \frac{P_t}{P_{\text{last close of prior year}}} - 1",
        related=("trailing-return", "relative-strength"),
    ),

    # =====================================================================
    # Markets & data
    # =====================================================================
    Entry(
        "kospi", "KOSPI", DATA, korean="코스피 (유가증권시장)",
        definition="Korea's main stock market (Korea Composite Stock Price Index) on the "
                   "Korea Exchange (KRX).",
        in_app="One of the two markets ranked. Listing from KRX via FinanceDataReader; "
               "Yahoo symbols end in .KS (e.g. 005930.KS).",
        related=("kospi-200", "ticker", "preferred-shares", "nasdaq"),
    ),
    Entry(
        "kospi-200", "KOSPI 200", DATA, korean="코스피 200",
        definition="An index of 200 large, liquid KOSPI companies — the benchmark for "
                   "most Korean index funds and sector ETFs.",
        related=("kospi", "benchmark", "sector-etf"),
    ),
    Entry(
        "nasdaq", "NASDAQ", DATA, korean="나스닥",
        definition="A US stock exchange known for technology and growth companies.",
        in_app="The NASDAQ universe is the 300 largest NASDAQ companies by market cap "
               "plus every Nasdaq-100 member.",
        related=("nasdaq-100", "kospi", "universe"),
    ),
    Entry(
        "nasdaq-100", "Nasdaq-100", DATA, aliases=("NDX", "Nasdaq 100"),
        korean="나스닥 100",
        definition="An index of the 100 largest non-financial companies listed on NASDAQ. "
                   "Membership is reviewed every December, with replacements during the "
                   "year.",
        in_app="All members are always in the NASDAQ snapshot (NDX ✓ column). The "
               "'Nasdaq-100' universe ranks the 100 among themselves, one line per "
               "company (GOOG folded into GOOGL). Membership is fetched from Nasdaq, then "
               "Wikipedia, then the last saved list.",
        related=("nasdaq", "universe", "peer-snapshot"),
    ),
    Entry(
        "peer-snapshot", "Peer snapshot", DATA, aliases=("snapshot",),
        korean="비교군 스냅샷",
        definition="A saved daily table of every company in a market's universe with all "
                   "factor inputs, used for ranking.",
        in_app="Built with 'python -m data.snapshot' or the sidebar button (a few minutes "
               "per market) and saved as Parquet in data/snapshots. Market Leaders, "
               "Company Analysis, the dashboard and Sector ETFs all rank against it. "
               "Rebuild daily for current rankings.",
        related=("universe", "nasdaq-100", "synthetic-data"),
    ),
    Entry(
        "synthetic-data", "Synthetic data", DATA, aliases=("demo data", "synthetic mode"),
        korean="합성 (데모) 데이터",
        definition="Made-up but realistic data generated by the app so every page works "
                   "without API keys or network access.",
        in_app="Turn on 'Force synthetic data' in the sidebar, or the app falls back to it "
               "(with a warning banner) when live sources are unreachable. Every number "
               "is fake.",
        related=("peer-snapshot", "kis-api"),
    ),
    Entry(
        "price-freshness", "Price freshness", DATA,
        aliases=("real-time", "delayed", "previous close", "intraday"),
        korean="시세 최신성 (실시간/지연/전일 종가)",
        definition="How current a quoted price is. Real-time: within a few minutes. "
                   "Delayed: intraday but some minutes old. Previous close: the last "
                   "completed session's closing price.",
        in_app="Company Analysis badge, judged from each quote's own timestamp: real-time "
               "if ≤ 3 minutes old during the session. With KIS keys quotes are real-time; "
               "free Yahoo quotes are near real-time for NASDAQ and ~20 minutes delayed "
               "for KRX.",
        related=("kis-api", "yahoo-finance", "trading-day"),
    ),
    Entry(
        "trading-day", "Trading day", DATA, korean="거래일",
        definition="A day the exchange is open. About 252 per year, 21 per month.",
        in_app="All horizons and annualizations use trading days (252 per year).",
        related=("trailing-return", "lookback"),
    ),
    Entry(
        "kis-api", "KIS Open API", DATA, aliases=("PyKis", "KIS", "python-kis"),
        korean="한국투자증권 Open API",
        definition="Korea Investment & Securities' brokerage API, used for account "
                   "holdings, real-time quotes and KRX price history.",
        in_app="Accessed through python-kis. Keys go in .env (APP_KEY, APP_SECRET, "
               "ACCOUNT_NO, KIS_ID); without them the KIS-based pages use synthetic data.",
        related=("synthetic-data", "price-freshness", "yahoo-finance"),
    ),
    Entry(
        "yahoo-finance", "Yahoo Finance (yfinance)", DATA, aliases=("yfinance", "Yahoo"),
        korean="야후 파이낸스",
        definition="A free financial data site; the yfinance library reads its prices, "
                   "fundamentals and analyst estimates.",
        in_app="Main free source for Company Analysis, peer snapshots and Sector ETFs. "
               "Unofficial and rate-limited — snapshot builds retry with backoff.",
        related=("finance-datareader", "proxy", "peer-snapshot"),
    ),
    Entry(
        "finance-datareader", "FinanceDataReader", DATA, aliases=("FDR",),
        definition="An open-source Python library for Korean and global market listings "
                   "and prices.",
        in_app="Used for the KOSPI listing (KRX) and the NASDAQ listing ranked by market "
               "value (Naver).",
        related=("yahoo-finance", "kospi", "nasdaq"),
    ),
    Entry(
        "proxy", "Proxy (free-data proxy)", DATA, aliases=("stand-in",),
        korean="대용치",
        definition="A substitute measure used when the ideal data isn't available.",
        in_app="Free sources lack consensus revision history and Korean foreign-ownership "
               "data, so revenue revision, operating-margin change and operating margin "
               "use proxies (listed in each entry and in Company Analysis' Note column). "
               "All peers use the same proxies, so rankings stay comparable.",
        related=("fundamentals-override", "revenue-revision", "op-margin-change",
                 "operating-margin", "carry-proxy"),
    ),
    Entry(
        "fundamentals-override", "Fundamentals override file", DATA,
        aliases=("fundamentals.csv", "override file"), korean="펀더멘털 덮어쓰기 파일",
        definition="An optional CSV or Parquet file whose values replace the snapshot's "
                   "for matching tickers — the place to plug in better data, such as real "
                   "consensus revisions from FnGuide/DataGuide.",
        in_app="data/fundamentals.csv (or FUNDAMENTALS_PATH). Any subset of metric "
               "columns; blank cells don't override. Rates as fractions (0.05 = 5%).",
        related=("proxy", "peer-snapshot"),
    ),
    Entry(
        "adr-currency", "ADR and currency conversion", DATA, aliases=("ADR", "FX"),
        korean="ADR 및 환율 변환",
        definition="An American Depositary Receipt (ADR) is a foreign company's stock "
                   "traded in the US, usually priced in dollars while the company reports "
                   "in its home currency.",
        in_app="Before dividing statement figures by market cap, the app converts them "
               "from the reporting currency to the trading currency at the latest rate.",
        related=("earnings-yield", "cash-flow-yield", "nasdaq"),
    ),
    Entry(
        "ticker", "Ticker (KRX code)", DATA, aliases=("symbol", "stock code", "KRX code"),
        korean="종목코드 / 티커",
        definition="A stock's short identifier. US tickers are letters (AAPL); Korean "
                   "stocks use 6-digit KRX codes (005930 = Samsung Electronics).",
        in_app="Search accepts tickers, English names and Korean names. Leading zeros on "
               "KRX codes are restored if a spreadsheet drops them.",
        related=("kospi", "preferred-shares"),
    ),
    Entry(
        "preferred-shares", "Preferred shares", DATA, aliases=("우선주",),
        korean="우선주",
        definition="A share class with priority on dividends, usually without voting "
                   "rights. In Korea their codes end in 5, 7, 9 or K (005935 = Samsung "
                   "Electronics preferred).",
        in_app="Excluded from the KOSPI universe so each company appears once.",
        related=("ticker", "kospi"),
    ),
    Entry(
        "percentage-point", "Percentage point (pp)", DATA, aliases=("pp", "%p"),
        korean="퍼센트포인트 (%p)",
        definition="The arithmetic difference between two percentages.",
        example="A margin going from 10% to 12% is +2 percentage points, but a +20% "
                "relative increase.",
        related=("basis-point", "op-margin-change", "relative-strength"),
    ),
    Entry(
        "basis-point", "Basis point (bp)", DATA, aliases=("bps", "bp"),
        korean="베이시스 포인트 (bp)",
        definition="One hundredth of a percentage point: 1 bp = 0.01% = 0.0001.",
        example="10 bps = 0.10%; on ₩10,000,000 traded that is ₩10,000.",
        related=("transaction-cost", "percentage-point"),
    ),
)
