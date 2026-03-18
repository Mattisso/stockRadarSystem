# Stock Radar System — Combined Specifications

> Consolidated from 6 specification documents: Trading Flow, Frontend Architecture, L1 Schema, L2 Schema, Master AI Build Prompt, and Frontend Layout Guide.

---

## Part 1: End-to-End Trading Flow Specification

### 1.1 System Objective

The system continuously monitors approximately 3,000 NASDAQ stocks priced below $10, detects early intraday breakout behavior, escalates promising candidates from Level 1 monitoring into Level 2 order-book confirmation, executes entries with controlled sizing, watches post-entry order flow for weakness, and exits automatically using profit, stop-loss, and failure logic. Each candidate, trade, and result is stored for later analytics and model training.

### 1.2 Canonical Flow Stages

1. **Universe load**: Once per trading day, build the tradable universe from NASDAQ symbols under $10.
2. **L1 monitoring**: Stream top-of-book and trade data for the full universe and maintain rolling intraday metrics.
3. **Candidate scoring**: Rank symbols using breakout features such as momentum, relative volume, spread quality, and approach to day high.
4. **Breakout escalation**: When a symbol crosses configured thresholds, subscribe to deeper L2 data for confirmation.
5. **Entry decision**: Validate bid support, ask consumption, spread quality, and execution safety before sending a buy order.
6. **Position watch**: After fill, continue tracking L2 strength, realized momentum, risk limits, and position performance.
7. **Exit decision**: Sell on target achievement, loss thresholds, failed breakout behavior, or weakening order-book structure.
8. **Persistence**: Save signal context, order details, book snapshots, and trade outcome labels for later reporting and machine learning.

### 1.3 Detailed Trading Lifecycle

#### 1.3.1 Universe Selection
- Universe is refreshed once near market open using NASDAQ-listed symbols priced below $10.
- Include metadata useful for ranking and risk checks: float, previous close, gap %, halt status.
- Do not remove a symbol intraday just because it trades above $10 after becoming in-play.

#### 1.3.2 Level 1 Monitoring
- L1 data is streamed or polled at high frequency for every symbol in the universe.
- Maintain rolling windows: 30-second, 1-minute, 3-minute, and 5-minute changes.
- Core L1 metrics: last price, bid, ask, spread, volume, relative volume, VWAP distance, day high proximity, % change, recent acceleration.

#### 1.3.3 Candidate Detection
- A symbol becomes an L1 candidate when it shows a combination of: rising price, high relative volume, increasing tape speed, narrow enough spread, and proximity to a breakout level.
- Candidate status is stateful: `Normal → Watching → Candidate → L2 Confirmation → Ready to Buy`
- Record why a symbol was promoted, including the features that crossed thresholds.

#### 1.3.4 Automatic L2 Subscription
- When a symbol becomes a serious candidate, automatically subscribe to L2 order-book updates.
- L2 subscription is on-demand to reduce cost and processing load across the entire universe.
- L2 monitoring begins before the buy so the system can confirm whether the breakout has genuine support.

#### 1.3.5 Buy Confirmation
- Entry requires more than raw price movement; the order book should show supportive behavior:
  - Strong bid stacking
  - Ask absorption
  - Repeated prints at or through resistance
  - Manageable spread
- Reject entries when: move is extended, spread widens abruptly, large ask walls appear overhead, or bid support disappears.
- All entry decisions return both a boolean decision and a reason payload for auditability.

#### 1.3.6 Position Monitoring After Fill
- After entry, the same L2 stream is reused to determine momentum continuation or weakening.
- Track: real-time P&L, distance from VWAP, nearest support, bid ladder health, whether buyers continue lifting offers.
- Hold state is explicit: `Hold → Reduce Confidence → Exit Soon → Sell Now`

#### 1.3.7 Sell Logic
- Primary sell conditions:
  - Hitting a profit target
  - Trailing weakness after a strong move
  - Stop-loss breach
  - Failed breakout
  - Daily risk shutdown
- Prioritize capital protection over maximum upside when book conditions deteriorate quickly.
- False breakout identified when: stock loses key bid support, fails to hold breakout level, or shows repeated downticks with thinning bids.

#### 1.3.8 Post-Trade Storage
- Store every decision stage: candidate creation, L2 confirmation, buy signal, order sent, fill received, exit signal, sell fill, final outcome.
- Persist both structured metrics and human-readable explanations (e.g., "Entry approved because bid stack strengthened at 3.48 and asks at 3.50 were repeatedly absorbed.")
- Trade results feed pattern-confidence scoring and model retraining.

### 1.4 State Machine

| State | Entry Condition | Exit Condition | Next States |
|---|---|---|---|
| Normal | Symbol in daily universe | No activity | Watching |
| Watching | Basic momentum or volume increase | Signal cools off | Normal, Candidate |
| Candidate | Breakout score exceeds threshold | Metrics fade | Watching, L2 Confirm |
| L2 Confirm | Supportive book and tape | Book fails | Candidate, Ready to Buy |
| Ready to Buy | Risk checks and entry pass | Risk/requote fail | In Position, Candidate |
| In Position | Order filled | Exit trigger hit | Exit Pending |
| Exit Pending | Sell order working | Order filled | Closed |
| Closed | Trade complete | N/A | Normal |

### 1.5 Decision Inputs by Stage

**L1 candidate score inputs:**
- Percent change from open and from recent rolling window
- Relative volume versus normal intraday pace
- Spread quality
- Distance to day high or key breakout level
- Trade acceleration / print frequency
- VWAP relationship
- Float and liquidity context

**L2 buy confirmation inputs:**
- Top-of-book bid and ask depth
- Bid stack strengthening versus weakening
- Ask absorption and removal
- Presence of large hidden or visible sell walls
- Aggressive lifting of offers
- Support directly below entry
- Execution safety and slippage estimate

**L2 sell/weakness inputs:**
- Loss of stacked bids
- Inability to hold breakout level
- Repeated hitting of bids
- Spread expansion
- Momentum stall after entry
- Failure to make higher highs
- Approach to max loss or trailing-stop condition

### 1.6 Persistence Requirements
- Store daily universe snapshots and eligibility fields.
- Store L1 rolling metrics per symbol at a configurable interval.
- Store every candidate event with timestamp and feature values.
- Store L2 snapshots around buy and sell decisions, especially 5–15 seconds before and after execution.
- Store orders, fills, cancel events, and broker responses.
- Store derived labels: runner, false breakout, strong continuation, weak exit.
- Store pattern confidence updates so the system can explain why confidence increased or decreased.

### 1.7 Non-Functional Expectations
- Favor determinism and explainability over black-box decisions in early versions.
- Every action should be reproducible from saved market data and logged thresholds.
- Frontend labels should use plain English descriptions in addition to raw scores.
- Failures (missing L2, stale data, rejected order, broker disconnect) must move the trade flow into safe states.

---

## Part 2: Frontend Functional and Technical Architecture

### 2.1 Product Design Principles
- Dashboard should feel like a **professional trading operations console**, not a static admin panel.
- Real-time views must distinguish between passive monitoring, candidate signals, active L2 watch, and live positions.
- Important decisions should be explainable in plain English next to quantitative scores.
- Latency-sensitive widgets should update live without manual refresh.
- UI should stay readable under load using clear hierarchy, color coding, and focused panels.

### 2.2 Primary Screens and Panels

| Screen | Description |
|---|---|
| **Dashboard** | Account summary, active positions, active signals, recent trades, system health, daily risk |
| **Universe Monitor** | Full sub-$10 NASDAQ universe with filters for momentum, volume, price, candidate state, watch status |
| **Signal Queue** | Symbols promoted to candidate/breakout states with score explanations and timestamps |
| **L2 Watch Panel** | Order-book panel for symbols under L2 confirmation or post-entry monitoring |
| **Positions** | Active holdings, entry price, current price, unrealized P&L, stop state, confidence state, recommended action |
| **Trade History** | Orders, fills, exits, reasons, post-trade outcomes with searchable logs |
| **Pattern Analytics** | Historical success rates by setup, time of day, price band, spread condition, L2 profile |
| **Risk Controls** | Max position size, max daily loss, kill switch, broker/data status, strategy toggles |
| **Settings / Connections** | Broker keys, data provider health, thresholds, paper/live mode, monitoring preferences |

### 2.3 Dashboard Layout

| Region | Contents |
|---|---|
| **Top bar** | Buying power, open positions, realized/unrealized P&L, active signals, risk state, feed health |
| **Left workspace** | Universe Monitor, filters, signal pipeline, candidate queue |
| **Right workspace** | Symbol detail, L2 ladder, pattern notes, position panel, order details |
| **Bottom strip** | Pattern confidence, recent outcomes, false breakout stats, hold times, exit reasons |

### 2.4 Functional Requirements

**Universe Monitor:**
- Columns: symbol, last price, % change, relative volume, spread, day-high distance, candidate score, current state.
- Filter by: price band, score threshold, spread max, liquidity minimum, state.
- Clicking a row opens that symbol in the detail and L2 panels.

**Signal Queue:**
- Each signal shows when the symbol entered candidate status and why.
- Display exact trigger reasons (e.g., "Relative volume > 4.2 and price within 0.8% of day high.")
- Sort by confidence, recency, and expected quality.

**L2 Watch Panel:**
- Display top bid/ask levels, sizes, imbalance, recent changes.
- Highlight supportive behavior: stacked bids, ask absorption, overhead ask walls.
- When selected symbol is in a live position, mark support and weakness signals.

**Positions:**
- Show entry price, current price, quantity, unrealized P&L, max favorable excursion, current exit state.
- Display plain-English status: "Holding: bids still stacked" or "Exit soon: support weakening."
- Quick access to detailed decision trail for each position.

**Pattern Analytics:**
- Summarize which patterns historically produced the best continuation after entry.
- Show win rate, average gain, average hold time, false-breakout rate by setup family.
- Allow drill-down into saved examples for model improvement.

**Risk Controls:**
- Always show whether trading is enabled, paused, or shut down by kill switch.
- Show remaining daily loss buffer and remaining deployable buying power.
- Surface degraded connection or rule states prominently in the header.

### 2.5 Technical Architecture
- **Frontend**: Angular application using feature modules, shared UI components, websocket-backed state services.
- **API style**: REST for historical data, configuration, and lookup endpoints; WebSocket for live L1, L2, orders, fills, and risk events.
- **Backend services**: universe service, L1 monitor service, candidate scoring engine, L2 subscription manager, execution service, analytics service, audit/logging service.
- **Database**: PostgreSQL for stored signals, trades, snapshots, outcomes, user settings, analytics tables.
- **Caching/state**: in-memory streaming state for live market data, with periodic persistence to database tables.

### 2.6 Frontend Component Map

| Component | Purpose | Inputs / Outputs |
|---|---|---|
| `dashboard-shell` | Main page layout and routing shell | Consumes global account and system state |
| `portfolio-summary-card` | Cash, buying power, P&L, exposure | Input: account summary model |
| `universe-table` | Live L1 table for full universe | Input: symbol rows; Output: symbolSelected |
| `signal-feed-panel` | Candidate and breakout list | Input: signal stream; Output: focusSignal |
| `symbol-detail-panel` | Selected symbol summary and explanation | Input: selected symbol aggregate |
| `l2-order-book-panel` | Top bid/ask levels and imbalance | Input: L2 snapshot stream |
| `position-monitor-panel` | Active positions and status | Input: position models; Output: close/request actions |
| `trade-history-panel` | Recent trades and audit trail | Input: fills/orders/history |
| `risk-status-banner` | Daily loss, kill switch, connection alarms | Input: risk and health state |
| `pattern-confidence-panel` | Historical setup confidence and insights | Input: analytics summaries |

### 2.7 TypeScript Model Contracts

```typescript
interface UniverseRow {
  symbol; lastPrice; pctChange; volume; relVolume; spread;
  vwap; dayHigh; candidateScore; state; updatedAt;
}

interface CandidateSignal {
  symbol; score; reasons[]; state; triggeredAt; l1Metrics;
}

interface L2Level {
  side; price; size; marketMaker?;
}

interface L2Snapshot {
  symbol; ts; bids: L2Level[]; asks: L2Level[];
  imbalance; supportPrice?; weaknessState?;
}

interface PositionView {
  symbol; qty; avgCost; lastPrice; unrealizedPnl;
  entryReason; exitState; confidenceText;
}

interface RiskState {
  tradingEnabled; mode; dailyLossUsed; dailyLossLimit;
  buyingPower; brokerConnected; dataConnected;
}
```

### 2.8 Data Refresh and Interaction Model
- Universe table and signal queue update continuously from websocket streams.
- Historical screens load initial data over REST, then subscribe for incremental live updates.
- Selections are stateful: clicking a symbol updates chart, explanation, L2, and position panels together.
- UI preserves user filters and selected symbol during live updates.

### 2.9 Visual Status Language

| State | Color |
|---|---|
| Normal / inactive | Neutral gray |
| Watching / early interest | Blue |
| Candidate / breakout building | Amber |
| Ready to buy / strong confirmation | Green |
| Weakening / exit soon | Orange |
| Stopped / failed / disconnected | Red |

---

## Part 3: Level 1 Market Data Schema

### 3.1 L1 Record Definition

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `symbol` | string | Y | Ticker symbol | LCID |
| `ts` | datetime | Y | Exchange or system timestamp | 2026-03-15T10:51:03.215Z |
| `lastPrice` | number | Y | Most recent trade price | 3.48 |
| `bid` | number | Y | Best bid price | 3.47 |
| `ask` | number | Y | Best ask price | 3.48 |
| `spread` | number | Y | ask - bid | 0.01 |
| `lastSize` | integer | N | Most recent trade size | 2500 |
| `dayVolume` | integer | Y | Cumulative intraday share volume | 12450321 |
| `relVolume` | number | Y | Current volume vs normal intraday pace | 5.2 |
| `pctChange` | number | Y | Percent change from previous close | 28.4 |
| `vwap` | number | Y | Volume-weighted average price | 3.29 |
| `dayHigh` | number | Y | Current day high | 3.50 |
| `dayLow` | number | Y | Current day low | 2.61 |
| `distanceToDayHighPct` | number | Y | % distance from last price to day high | 0.57 |
| `floatShares` | integer | N | Public float estimate | 15400000 |
| `marketCap` | integer | N | Market cap estimate | 62000000 |
| `haltStatus` | string | Y | Normal, LUDP, Halted, Resume Pending | Normal |
| `candidateScore` | number | N | Composite L1 breakout score | 0.81 |
| `state` | string | Y | Normal, Watching, Candidate, L2 Confirm, ReadyToBuy | Candidate |
| `reasonText` | string | N | Plain-English explanation of current state | High RVOL and pressing day high |

### 3.2 Derived L1 Metrics for Candidate Scoring

| Metric | Description |
|---|---|
| `priceAcceleration1m` | Percent change over the last 1 minute |
| `priceAcceleration3m` | Percent change over the last 3 minutes |
| `volumeBurstRatio` | Short-window volume versus recent rolling average |
| `vwapDistancePct` | Percent above or below VWAP |
| `spreadQualityScore` | Normalized score favoring tighter spreads |
| `breakoutPressureScore` | Combined measure of day-high proximity, acceleration, and liquidity quality |

### 3.3 Example L1 JSON Payloads

**Candidate (LCID):**
```json
{
  "symbol": "LCID", "ts": "2026-03-15T10:51:03.215Z",
  "lastPrice": 3.48, "bid": 3.47, "ask": 3.48, "spread": 0.01,
  "dayVolume": 12450321, "relVolume": 5.2, "pctChange": 28.4,
  "vwap": 3.29, "dayHigh": 3.5, "dayLow": 2.61,
  "distanceToDayHighPct": 0.57, "candidateScore": 0.81,
  "state": "Candidate",
  "reasonText": "High RVOL, tight spread, and pressing day high."
}
```

**Watching (ABUS):**
```json
{
  "symbol": "ABUS", "ts": "2026-03-15T10:51:03.215Z",
  "lastPrice": 2.14, "bid": 2.13, "ask": 2.15, "spread": 0.02,
  "dayVolume": 4812300, "relVolume": 2.1, "pctChange": 11.3,
  "vwap": 2.08, "dayHigh": 2.2, "dayLow": 1.91,
  "distanceToDayHighPct": 2.73, "candidateScore": 0.42,
  "state": "Watching",
  "reasonText": "Momentum improving, but not yet near breakout."
}
```

**L2 Confirm (GEVO):**
```json
{
  "symbol": "GEVO", "ts": "2026-03-15T10:51:03.215Z",
  "lastPrice": 1.88, "bid": 1.87, "ask": 1.88, "spread": 0.01,
  "dayVolume": 16422001, "relVolume": 7.3, "pctChange": 35.7,
  "vwap": 1.73, "dayHigh": 1.89, "dayLow": 1.42,
  "distanceToDayHighPct": 0.53, "candidateScore": 0.91,
  "state": "L2 Confirm",
  "reasonText": "Very strong volume and near break with clean spread."
}
```

### 3.4 Example Universe Table

| Symbol | Last | % Chg | Rel Vol | Spread | Day High Dist % | Score | State |
|---|---|---|---|---|---|---|---|
| LCID | 3.48 | 28.4 | 5.2 | 0.01 | 0.57 | 0.81 | Candidate |
| GEVO | 1.88 | 35.7 | 7.3 | 0.01 | 0.53 | 0.91 | L2 Confirm |
| ABUS | 2.14 | 11.3 | 2.1 | 0.02 | 2.73 | 0.42 | Watching |
| CLOV | 3.07 | 16.2 | 3.8 | 0.02 | 1.15 | 0.67 | Candidate |
| DATS | 4.21 | 41.9 | 8.4 | 0.03 | 0.24 | 0.95 | ReadyToBuy |

### 3.5 Example State Progression (LCID)

| Time | Last | Rel Vol | Score | State / Explanation |
|---|---|---|---|---|
| 10:42:05 | 3.18 | 1.6 | 0.22 | Watching — volume rising but not near break |
| 10:46:19 | 3.31 | 2.9 | 0.49 | Watching — acceleration improving |
| 10:49:07 | 3.41 | 4.4 | 0.71 | Candidate — near resistance with tight spread |
| 10:50:28 | 3.47 | 5.0 | 0.85 | L2 Confirm — pressing day high; subscribe to book |
| 10:51:03 | 3.48 | 5.2 | 0.81 | Candidate — waiting for stronger book support |
| 10:51:19 | 3.50 | 5.5 | 0.93 | ReadyToBuy — break confirmed on tape/L2 |

### 3.6 L1 Developer Notes
- Keep raw exchange/provider fields separate from derived strategy fields.
- Prefer stable field names in camelCase across backend and frontend contracts.
- Do not compute irreversible trading actions on the frontend from L1 alone; use L1 as context and ranking input.
- When replaying historical data, preserve original timestamps and ordering.

---

## Part 4: Level 2 Order Book Schema

### 4.1 L2 Data Model

```typescript
interface L2Level {
  side: 'bid' | 'ask';
  price: number;
  size: number;
  marketMaker?: string;
  orderCount?: number;
}

interface L2Snapshot {
  symbol: string;
  ts: string;
  bids: L2Level[];
  asks: L2Level[];
  spread: number;
  bidSizeTotalTop5: number;
  askSizeTotalTop5: number;
  imbalanceRatio: number;
  supportPrice?: number;
  resistancePrice?: number;
  confirmationState: string;
  weaknessState?: string;
  explanation?: string;
}

interface L2Event {
  symbol: string;
  ts: string;
  eventType: string;
  explanation: string;
  metrics: Record<string, number | string>;
}
```

### 4.2 Core L2 Fields

| Field | Type | Required | Description | Example |
|---|---|---|---|---|
| `symbol` | string | Y | Ticker under L2 watch | LCID |
| `ts` | datetime | Y | Timestamp of snapshot or event | 2026-03-15T10:51:19.480Z |
| `bids` | array | Y | Ordered best-to-worst bid levels | [{3.49, 21000}, ...] |
| `asks` | array | Y | Ordered best-to-worst ask levels | [{3.50, 14500}, ...] |
| `spread` | number | Y | Best ask - best bid | 0.01 |
| `bidSizeTotalTop5` | integer | Y | Sum of top 5 bid sizes | 79200 |
| `askSizeTotalTop5` | integer | Y | Sum of top 5 ask sizes | 46600 |
| `imbalanceRatio` | number | Y | bidSizeTotalTop5 / askSizeTotalTop5 | 1.70 |
| `supportPrice` | number | N | Nearest support price level | 3.48 |
| `resistancePrice` | number | N | Nearest overhead resistance or wall | 3.52 |
| `confirmationState` | string | Y | Watching, Confirmed, Weak, ExitSoon, SellNow | Confirmed |
| `weaknessState` | string | N | Weakness flag if active | Bids thinning at entry support |
| `explanation` | string | N | Human-readable L2 interpretation | Bids stacked below 3.50 and asks getting hit |

### 4.3 Buy Confirmation Signals
- **Bid stacking**: more size appears at or just below support as price presses higher.
- **Ask absorption**: repeated executions into the same ask level without major pullback.
- **Offer lifting**: buyers consistently remove asks rather than waiting on bids.
- **Healthy imbalance**: total top-of-book bid size meaningfully stronger than ask size.
- **Contained spread**: spread remains tight enough to avoid poor entry quality.
- **Low overhead wall risk**: no immediate large ask wall likely to cap the move.

### 4.4 Sell / Weakness Signals
- **Bid thinning**: top bid levels shrink as price stalls or downticks.
- **Support loss**: breakout level or entry support no longer defended.
- **Repeated hitting of bids**: prints occur on bid side instead of through the ask.
- **Ask wall appearance**: large seller appears overhead, price repeatedly fails there.
- **Spread expansion**: spread widens abruptly, indicating weaker execution quality.
- **Momentum stall**: price stops making higher highs while book support degrades.

### 4.5 Example: Bullish Breakout Confirmation (LCID)

```json
{
  "symbol": "LCID", "ts": "2026-03-15T10:51:19.480Z",
  "bids": [
    {"side": "bid", "price": 3.49, "size": 21000, "marketMaker": "ARCA"},
    {"side": "bid", "price": 3.48, "size": 18500, "marketMaker": "NSDQ"},
    {"side": "bid", "price": 3.47, "size": 14300, "marketMaker": "BATS"},
    {"side": "bid", "price": 3.46, "size": 13200, "marketMaker": "EDGX"},
    {"side": "bid", "price": 3.45, "size": 12200, "marketMaker": "IEX"}
  ],
  "asks": [
    {"side": "ask", "price": 3.50, "size": 14500, "marketMaker": "ARCA"},
    {"side": "ask", "price": 3.51, "size": 11200, "marketMaker": "NSDQ"},
    {"side": "ask", "price": 3.52, "size": 9800, "marketMaker": "BATS"},
    {"side": "ask", "price": 3.53, "size": 6100, "marketMaker": "EDGX"},
    {"side": "ask", "price": 3.54, "size": 5000, "marketMaker": "IEX"}
  ],
  "spread": 0.01,
  "bidSizeTotalTop5": 79200, "askSizeTotalTop5": 46600,
  "imbalanceRatio": 1.7,
  "supportPrice": 3.48, "resistancePrice": 3.52,
  "confirmationState": "Confirmed",
  "explanation": "Bids stacked below 3.50 and asks are being absorbed at the break."
}
```

### 4.6 Example: False Breakout Setup (DATS)

```json
{
  "symbol": "DATS", "ts": "2026-03-15T10:54:08.112Z",
  "bids": [
    {"side": "bid", "price": 4.18, "size": 7200},
    {"side": "bid", "price": 4.17, "size": 4100},
    {"side": "bid", "price": 4.16, "size": 3900},
    {"side": "bid", "price": 4.15, "size": 3200},
    {"side": "bid", "price": 4.14, "size": 2800}
  ],
  "asks": [
    {"side": "ask", "price": 4.19, "size": 14800},
    {"side": "ask", "price": 4.20, "size": 22100},
    {"side": "ask", "price": 4.21, "size": 17900},
    {"side": "ask", "price": 4.22, "size": 12200},
    {"side": "ask", "price": 4.23, "size": 8600}
  ],
  "spread": 0.01,
  "bidSizeTotalTop5": 21200, "askSizeTotalTop5": 75600,
  "imbalanceRatio": 0.28,
  "supportPrice": 4.17, "resistancePrice": 4.20,
  "confirmationState": "Weak",
  "weaknessState": "Overhead ask wall and thin bids",
  "explanation": "Break attempt is likely false; asks dominate and support is shallow."
}
```

### 4.7 Example: Post-Entry Exit Soon (GEVO)

```json
{
  "symbol": "GEVO", "ts": "2026-03-15T11:02:14.901Z",
  "bids": [
    {"side": "bid", "price": 1.93, "size": 6400},
    {"side": "bid", "price": 1.92, "size": 5500},
    {"side": "bid", "price": 1.91, "size": 4200},
    {"side": "bid", "price": 1.90, "size": 3600},
    {"side": "bid", "price": 1.89, "size": 2800}
  ],
  "asks": [
    {"side": "ask", "price": 1.94, "size": 9000},
    {"side": "ask", "price": 1.95, "size": 11300},
    {"side": "ask", "price": 1.96, "size": 12100},
    {"side": "ask", "price": 1.97, "size": 8700},
    {"side": "ask", "price": 1.98, "size": 7600}
  ],
  "spread": 0.01,
  "bidSizeTotalTop5": 22500, "askSizeTotalTop5": 48700,
  "imbalanceRatio": 0.46,
  "supportPrice": 1.92, "resistancePrice": 1.95,
  "confirmationState": "ExitSoon",
  "weaknessState": "Bids thinning and unable to reclaim highs",
  "explanation": "Still above stop, but momentum is fading and support below entry is weakening."
}
```

### 4.8 Example L2 Event Stream

| Time | Event Type | Meaning | Explanation |
|---|---|---|---|
| 10:51:11 | `ask_absorbed` | Resistance level getting consumed | 3.50 ask refreshed and absorbed three times |
| 10:51:18 | `bid_stack_up` | Support building | Size increased at 3.48 and 3.49 while price held |
| 10:54:09 | `ask_wall_detected` | Overhead seller risk | 4.20 ask grew from 7k to 22k |
| 11:02:13 | `bid_thin` | Support deteriorating | Top two bid levels lost 40% of size in 8 seconds |
| 11:02:14 | `exit_warning` | Auto-sell condition nearing | Momentum stalled and bids no longer supporting |

### 4.9 L2 Developer Notes
- Store both snapshots and meaningful micro-events (easier than replaying raw ladders).
- Frontend renders top 5 levels initially; backend may store deeper ladders.
- Use the explanation field to convert raw order-book behavior into plain English.
- Entry and exit logic should log which specific L2 rules fired, not just the final action.
- Early versions use top 5 levels per side; deeper ladders can be added later without changing the core model.

---

## Part 5: Master AI Frontend Build Prompt

### 5.1 Source of Truth Priority
When conflicts arise between documents:
**Data Schema → Architecture → Flow → Assumptions**

### 5.2 Core Architectural Rules

**Universe Handling:**
- Symbol universe loaded once per trading session.
- System does NOT continuously rebuild the universe.
- All intraday processing operates on this fixed set.

**Continuous Processes (must run in real time):**
- L1 data updates
- Candidate scoring
- Breakout detection
- L2 monitoring
- Position tracking
- Sell logic and risk enforcement

**Separation of Concerns (independent domains):**
- L1 data stream
- L2 data stream
- Signal state machine
- Trade execution state
- Portfolio / positions
- Risk system

### 5.3 Required Frontend Models

| Model | Purpose |
|---|---|
| `DailyUniverseSymbol` | Universe symbol with metadata |
| `L1Tick` | Level 1 market data tick |
| `BreakoutSignal` | Candidate/breakout signal with reasons |
| `L2Snapshot` | Level 2 order book snapshot |
| `L2Level` | Single price level in the book |
| `Position` | Open position with P&L |
| `OrderEvent` | Order lifecycle event |
| `TradeResult` | Completed trade with outcome |
| `PatternMetric` | Historical pattern performance |
| `RiskState` | System risk state |
| `SystemHealth` | Connection and feed health |

### 5.4 Suggested Angular Project Structure

```
core/
shared/
features/dashboard/
features/universe/
features/signals/
features/l2-monitor/
features/positions/
features/analytics/
features/risk/
features/settings/
services/
models/
mocks/
```

### 5.5 UI Behavior Standards
- Real-time updates must not cause UI flickering.
- State changes must be visually clear.
- Use consistent color logic across modules.
- Use badges for signal state.
- Use expandable panels or side drawers for detail.
- Show timestamps consistently.
- Display reason codes for buy and sell decisions.

### 5.6 Mock-First Development
- Entire application must function without a backend initially.
- Use mock JSON data derived from L1 and L2 schema examples.
- All UI flows must be testable using mock services.
- Services designed for easy replacement of mock data with websocket streams — no UI rewrite required.

### 5.7 Non-Goals
- Do NOT merge L1 and L2 data models.
- Do NOT continuously rebuild the universe list.
- Do NOT invent fields not defined in the schema.
- Do NOT combine signal logic with UI logic.

---

## Part 6: Frontend Layout and Starter Package Guide

### 6.1 Layout Objective
The frontend should feel like a real trading workstation. Visual priority:
1. Immediate awareness of active opportunities
2. Fast interpretation of signal progression
3. Clear display of Level 2 strength or weakness
4. Always-visible position and risk information
5. Analytics that build confidence in the strategy over time

### 6.2 Screen Regions

| Region | Purpose | Contents |
|---|---|---|
| **Top bar** | Always-visible operating summary | Buying power, open positions, realized/unrealized P&L, active signals, risk state, feed health |
| **Left workspace** | Discovery and monitoring | Universe Monitor, filters, signal pipeline, candidate queue |
| **Right workspace** | Decision support and execution context | Symbol detail, L2 ladder, pattern notes, position panel, order details |
| **Bottom strip** | Trust-building analytics | Pattern confidence, recent outcomes, false breakout stats, hold times, exit reasons |

### 6.3 Dashboard Composition

**Top Summary Bar:**
Account value, buying power, open positions count, active L1 candidates, active L2 confirmations, daily P&L, risk state badge, market data/broker health.

**Left Column:**
Universe Monitor table, quick filters (price, % change, RVOL, spread, status), Signal Pipeline panel, hot candidates list.

**Center / Main Detail Area:**
Selected symbol header, L1 snapshot cards, L2 ladder, breakout reasoning panel, execution timeline, position health summary.

**Bottom Analytics Strip:**
Recent trade outcomes, pattern win rate, false breakout count, average gain/loss, confidence trend.

### 6.4 Navigation and Routing
- Dashboard as the default landing route.
- Dedicated routes for Universe, Signals, Positions, Analytics, Risk, Settings.
- Selected symbol opens in a side drawer or right-hand detail route outlet.
- User should stay on the main dashboard for most activity without constant page switching.

### 6.5 Visual Design Guidance
- Professional dark-on-light or muted dark theme with strong contrast for critical signals.
- Badges for state transitions: Candidate, L2 Confirm, Ready, In Position, Exit Pending.
- Restrained color system: green (strength), amber (caution), red (risk), blue (neutral system state).
- Soft card corners, generous spacing — premium feel, not cramped.
- Table readability prioritized; avoid visual clutter in real-time areas.
- Plain-English labels beside raw metrics wherever possible.

### 6.6 Recommended Build Order
1. Create shared models and mock data first.
2. Build layout shell and routing next.
3. Implement top summary cards and Universe Monitor.
4. Add Signal Pipeline and selected-symbol detail area.
5. Add L2 ladder visualization and positions panel.
6. Finish with analytics, risk, and settings screens.
7. Only after the UI works end-to-end in mock mode should live integrations be added.

### 6.7 Non-Goals for Starter Package
- Do not build a final broker integration layer yet.
- Do not hardcode business logic into presentational components.
- Do not merge L1 and L2 into one oversimplified data object.
- Do not over-engineer authentication or deployment in version 1.
