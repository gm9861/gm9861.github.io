#!/usr/bin/env python3
"""
WDD Dashboard - Web UI for Solana Token Monitor
"""

import json
import math
import urllib.request
from datetime import datetime, timezone
from flask import Flask, render_template_string, Response

app = Flask(__name__)

TOKEN_ADDRESS = "6iA73gpVFE4HL1DqJoRJGGz1YbPwaFwm3Nt4gFPump"
MAIN_POOL_ADDRESS = "9RpsV1vWy6itWjiHsBjrbpw2Z36AeiCnaiktyqTnXxcr"
NETWORK = "solana"

# ──────────────────────────────────────────────
# Data fetching
# ──────────────────────────────────────────────

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def fetch_token_data():
    url = f"https://api.geckoterminal.com/api/v2/networks/{NETWORK}/tokens/{TOKEN_ADDRESS}"
    return fetch_json(url)

def fetch_pool_data():
    url = f"https://api.geckoterminal.com/api/v2/networks/{NETWORK}/pools/{MAIN_POOL_ADDRESS}"
    return fetch_json(url)

def safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def format_usd(val):
    try:
        v = float(val)
        if v >= 1_000_000_000:
            return f"${v/1_000_000_000:.2f}B"
        elif v >= 1_000_000:
            return f"${v/1_000_000:.2f}M"
        elif v >= 1_000:
            return f"${v:,.2f}"
        else:
            return f"${v:.6f}"
    except:
        return "$--"

def format_pct(val):
    try:
        v = float(val)
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.3f}%"
    except:
        return "--"

def color_pct(val):
    try:
        v = float(val)
        if v > 0:
            return "#22c55e"
        elif v < 0:
            return "#ef4444"
        else:
            return "#6b7280"
    except:
        return "#6b7280"

def calc_sentiment(token_attrs, pool_attrs):
    pc = pool_attrs.get("price_change_percentage", {})
    tx = pool_attrs.get("transactions", {})
    vol = pool_attrs.get("volume_usd", {})
    reserve = safe_float(pool_attrs.get("reserve_in_usd", 0))
    market_cap = safe_float(token_attrs.get("market_cap_usd", 0))

    m5  = safe_float(pc.get("m5", 0))
    m15 = safe_float(pc.get("m15", 0))
    m30 = safe_float(pc.get("m30", 0))
    h1  = safe_float(pc.get("h1", 0))
    h6  = safe_float(pc.get("h6", 0))
    h24 = safe_float(pc.get("h24", 0))

    h1_buys   = tx.get("h1", {}).get("buys", 0)
    h1_sells  = tx.get("h1", {}).get("sells", 0)
    h1_buyers = tx.get("h1", {}).get("buyers", 0)
    h1_sellers= tx.get("h1", {}).get("sellers", 0)
    h24_buys  = tx.get("h24", {}).get("buys", 0)
    h24_sells = tx.get("h24", {}).get("sells", 0)

    h1_vol  = safe_float(vol.get("h1", 0))
    h24_vol = safe_float(vol.get("h24", 0))

    h1_buy_ratio  = h1_buys  / h1_sells  if h1_sells  > 0 else float(h1_buys)
    h24_buy_ratio = h24_buys / h24_sells if h24_sells > 0 else float(h24_buys)
    composite_ratio = h1_buy_ratio * 0.4 + h24_buy_ratio * 0.6

    short_avg = (m5 + m15 + m30) / 3
    mid_avg   = (h1 + h6) / 2
    if short_avg > 0 and mid_avg > 0:
        trend = "强烈看涨"
        trend_score = 15
    elif short_avg < 0 and mid_avg < 0:
        trend = "强烈看跌"
        trend_score = -15
    else:
        trend = "中性"
        trend_score = 0

    avg_hourly_vol = h24_vol / 24
    vol_ratio = h1_vol / avg_hourly_vol if avg_hourly_vol > 0 else 1.0
    if vol_ratio > 2:
        vol_sentiment = "放量活跃"
        vol_score = 10
    elif vol_ratio < 0.5:
        vol_sentiment = "缩量冷淡"
        vol_score = -10
    else:
        vol_sentiment = "正常"
        vol_score = 0

    liq_ratio = reserve / market_cap if market_cap > 0 else 0
    if liq_ratio > 0.1:
        liq_sentiment = "健康"
    elif liq_ratio < 0.05:
        liq_sentiment = "偏薄"
    else:
        liq_sentiment = "正常"

    base_score = 50
    if composite_ratio >= 1.0:
        buy_sell_score = min(25, (composite_ratio - 1.0) * 25)
    else:
        buy_sell_score = max(-25, (composite_ratio - 1.0) * 25)

    total = base_score + buy_sell_score + trend_score + vol_score
    total = max(0, min(100, total))

    if total >= 80:
        emoji = "极度FOMO"
        emoji_color = "#f97316"
    elif total >= 65:
        emoji = "强烈看涨"
        emoji_color = "#22c55e"
    elif total >= 55:
        emoji = "温和看涨"
        emoji_color = "#84cc16"
    elif total >= 45:
        emoji = "中性观望"
        emoji_color = "#6b7280"
    elif total >= 35:
        emoji = "温和看跌"
        emoji_color = "#eab308"
    elif total >= 20:
        emoji = "强烈看跌"
        emoji_color = "#f97316"
    else:
        emoji = "极度恐慌"
        emoji_color = "#ef4444"

    return {
        "m5": m5, "m15": m15, "m30": m30,
        "h1": h1, "h6": h6, "h24": h24,
        "h1_buys": h1_buys, "h1_sells": h1_sells,
        "h1_buyers": h1_buyers, "h1_sellers": h1_sellers,
        "h24_buys": h24_buys, "h24_sells": h24_sells,
        "h1_vol": h1_vol, "h24_vol": h24_vol,
        "reserve": reserve,
        "composite_ratio": composite_ratio,
        "h1_buy_ratio": h1_buy_ratio,
        "h24_buy_ratio": h24_buy_ratio,
        "trend": trend,
        "vol_sentiment": vol_sentiment,
        "vol_ratio": vol_ratio,
        "liq_sentiment": liq_sentiment,
        "liq_ratio": liq_ratio,
        "total": total,
        "emoji": emoji,
        "emoji_color": emoji_color,
    }

def get_data():
    """Fetch and process all data for the dashboard."""
    try:
        token_data = fetch_token_data()
        pool_data  = fetch_pool_data()
    except Exception as e:
        return {"error": str(e)}

    attrs = token_data.get("data", {}).get("attributes", {})
    pool_attrs = pool_data.get("data", {}).get("attributes", {})

    sentiment = calc_sentiment(attrs, pool_attrs)

    name = attrs.get("name", "Unknown")
    symbol = attrs.get("symbol", "Unknown")
    price_usd = safe_float(attrs.get("price_usd", 0))
    market_cap = attrs.get("market_cap_usd", "0")
    volume_h24 = attrs.get("volume_usd", {}).get("h24", "0")

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return {
        "name": name,
        "symbol": symbol,
        "price_usd": price_usd,
        "market_cap": format_usd(market_cap),
        "volume_h24": format_usd(volume_h24),
        "reserve": format_usd(sentiment["reserve"]),
        "now": now_utc,
        "error": None,
        **sentiment
    }

# ──────────────────────────────────────────────
# HTML Template
# ──────────────────────────────────────────────

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WDD Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    min-height: 100vh;
    padding: 20px;
  }
  .container { max-width: 900px; margin: 0 auto; }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }
  .header h1 { font-size: 24px; color: #f8fafc; }
  .header .updated { font-size: 13px; color: #64748b; }
  .header .refresh-btn {
    background: #1e293b;
    border: 1px solid #334155;
    color: #e2e8f0;
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
  }
  .refresh-btn:hover { background: #334155; }

  .error {
    background: #7f1d1d;
    border: 1px solid #b91c1c;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    color: #fca5a5;
  }

  .token-info {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }
  .card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
  }
  .card .label { font-size: 12px; color: #64748b; margin-bottom: 6px; text-transform: uppercase; }
  .card .value { font-size: 22px; font-weight: 700; color: #f8fafc; }
  .card .sub { font-size: 12px; color: #64748b; margin-top: 4px; }

  .price-card {
    grid-column: span 3;
    text-align: center;
  }
  .price-card .value { font-size: 36px; }

  /* Sentiment Gauge */
  .sentiment-section {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 12px;
  }
  .sentiment-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
  .gauge-wrap { flex: 1; }
  .gauge-bg {
    height: 12px;
    background: #334155;
    border-radius: 6px;
    overflow: hidden;
    position: relative;
  }
  .gauge-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.6s ease;
  }
  .gauge-labels { display: flex; justify-content: space-between; font-size: 11px; color: #64748b; margin-top: 6px; }
  .sentiment-score { font-size: 56px; font-weight: 800; line-height: 1; }
  .sentiment-label { font-size: 20px; font-weight: 600; margin-top: 4px; }

  /* Indicators row */
  .indicators {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 12px;
  }
  .indicator-card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
  }
  .indicator-card .ind-label { font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 8px; }
  .indicator-card .ind-value { font-size: 18px; font-weight: 700; }

  /* Price changes */
  .price-changes {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
  }
  .section-title { font-size: 13px; color: #64748b; text-transform: uppercase; margin-bottom: 14px; }
  .pc-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 8px;
  }
  .pc-item { text-align: center; }
  .pc-item .period { font-size: 11px; color: #64748b; margin-bottom: 4px; }
  .pc-item .pct { font-size: 15px; font-weight: 600; }

  /* Transactions */
  .transactions {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
  }
  .tx-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }
  .tx-box {
    background: #0f1117;
    border-radius: 8px;
    padding: 14px;
    text-align: center;
  }
  .tx-box .tx-label { font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 8px; }
  .tx-box .tx-value { font-size: 22px; font-weight: 700; }
  .tx-box .tx-ratio { font-size: 12px; color: #64748b; margin-top: 4px; }

  /* Liquidity */
  .liquidity {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 12px;
  }
  .liq-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  .liq-item { text-align: center; }
  .liq-item .liq-label { font-size: 11px; color: #64748b; text-transform: uppercase; margin-bottom: 6px; }
  .liq-item .liq-value { font-size: 18px; font-weight: 700; }

  /* Loading skeleton */
  .loading { text-align: center; padding: 60px; color: #64748b; }

  @media (max-width: 600px) {
    .token-info { grid-template-columns: 1fr; }
    .price-card { grid-column: span 1; }
    .pc-grid { grid-template-columns: repeat(3, 1fr); }
    .indicators { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <div>
      <h1>🪙 WDD Dashboard</h1>
      <div class="updated">最后更新: <span id="updated-time">{{ now }}</span></div>
    </div>
    <button class="refresh-btn" onclick="fetchData()">🔄 刷新</button>
  </div>

  <div id="app">
    {% if error %}
    <div class="error">
      ⚠️ 数据获取失败<br><small>{{ error }}</small>
    </div>
    {% else %}
    <!-- Token Info -->
    <div class="token-info">
      <div class="card price-card">
        <div class="label">价格 (USD)</div>
        <div class="value">${{ "%.8f"|format(price_usd) }}</div>
        <div class="sub">{{ name }} {{ symbol }}</div>
      </div>
    </div>
    <div class="token-info">
      <div class="card">
        <div class="label">市值</div>
        <div class="value">{{ market_cap }}</div>
      </div>
      <div class="card">
        <div class="label">24h 成交量</div>
        <div class="value">{{ volume_h24 }}</div>
      </div>
      <div class="card">
        <div class="label">流动性池</div>
        <div class="value">{{ reserve }}</div>
      </div>
    </div>

    <!-- Sentiment -->
    <div class="sentiment-section">
      <div class="section-title">😀 综合情绪指标</div>
      <div class="sentiment-header">
        <div class="gauge-wrap">
          <div class="gauge-bg">
            <div class="gauge-fill" style="width: {{ total }}%; background: {{ emoji_color }};"></div>
          </div>
          <div class="gauge-labels"><span>0 恐慌</span><span>100 FOMO</span></div>
        </div>
        <div style="text-align:center;">
          <div class="sentiment-score" style="color: {{ emoji_color }};">{{ total|int }}</div>
          <div class="sentiment-label" style="color: {{ emoji_color }};">{{ emoji }}</div>
        </div>
      </div>
    </div>

    <!-- Indicators -->
    <div class="indicators">
      <div class="indicator-card">
        <div class="ind-label">买卖压力比</div>
        <div class="ind-value" style="color: {% if composite_ratio > 1 %}#22c55e{% elif composite_ratio < 1 %}#ef4444{% else %}#6b7280{% endif %};">
          {{ "%.2f"|format(composite_ratio) }}x
        </div>
      </div>
      <div class="indicator-card">
        <div class="ind-label">趋势</div>
        <div class="ind-value">{{ trend }}</div>
      </div>
      <div class="indicator-card">
        <div class="ind-label">成交量情绪</div>
        <div class="ind-value">{{ vol_sentiment }}</div>
      </div>
    </div>

    <!-- Price Changes -->
    <div class="price-changes">
      <div class="section-title">📉 价格变化</div>
      <div class="pc-grid">
        <div class="pc-item">
          <div class="period">5分钟</div>
          <div class="pct" style="color: {{ color_pct(m5) }};">{{ format_pct(m5) }}</div>
        </div>
        <div class="pc-item">
          <div class="period">15分钟</div>
          <div class="pct" style="color: {{ color_pct(m15) }};">{{ format_pct(m15) }}</div>
        </div>
        <div class="pc-item">
          <div class="period">30分钟</div>
          <div class="pct" style="color: {{ color_pct(m30) }};">{{ format_pct(m30) }}</div>
        </div>
        <div class="pc-item">
          <div class="period">1小时</div>
          <div class="pct" style="color: {{ color_pct(h1) }};">{{ format_pct(h1) }}</div>
        </div>
        <div class="pc-item">
          <div class="period">6小时</div>
          <div class="pct" style="color: {{ color_pct(h6) }};">{{ format_pct(h6) }}</div>
        </div>
        <div class="pc-item">
          <div class="period">24小时</div>
          <div class="pct" style="color: {{ color_pct(h24) }};">{{ format_pct(h24) }}</div>
        </div>
      </div>
    </div>

    <!-- Transactions -->
    <div class="transactions">
      <div class="section-title">🔄 链上交易</div>
      <div class="tx-grid">
        <div class="tx-box">
          <div class="tx-label">1小时买入</div>
          <div class="tx-value" style="color:#22c55e;">{{ h1_buys }}</div>
          <div class="tx-label" style="margin-top:8px;">1小时卖出</div>
          <div class="tx-value" style="color:#ef4444;">{{ h1_sells }}</div>
          <div class="tx-ratio">买家 {{ h1_buyers }} | 卖家 {{ h1_sellers }}</div>
        </div>
        <div class="tx-box">
          <div class="tx-label">24小时买入</div>
          <div class="tx-value" style="color:#22c55e;">{{ h24_buys }}</div>
          <div class="tx-label" style="margin-top:8px;">24小时卖出</div>
          <div class="tx-value" style="color:#ef4444;">{{ h24_sells }}</div>
          <div class="tx-ratio">买卖比 {{ "%.2f"|format(h24_buy_ratio) }}x</div>
        </div>
      </div>
    </div>

    <!-- Liquidity -->
    <div class="liquidity">
      <div class="section-title">💧 流动性健康度</div>
      <div class="liq-grid">
        <div class="liq-item">
          <div class="liq-label">池子规模</div>
          <div class="liq-value">{{ reserve }}</div>
        </div>
        <div class="liq-item">
          <div class="liq-label">市值/流动性比</div>
          <div class="liq-value">{{ "%.2f"|format(liq_ratio) if liq_ratio > 0 else "--" }}</div>
        </div>
        <div class="liq-item">
          <div class="liq-label">健康状态</div>
          <div class="liq-value" style="color: {% if liq_sentiment == '健康' %}#22c55e{% elif liq_sentiment == '偏薄' %}#ef4444{% else %}#eab308{% endif %};">
            {{ liq_sentiment }}
          </div>
        </div>
      </div>
    </div>
    {% endif %}
  </div>
</div>

<script>
let loading = false;

async function fetchData() {
  if (loading) return;
  loading = true;
  document.getElementById('app').innerHTML = '<div class="loading">加载中...</div>';
  try {
    const resp = await fetch('/api/data');
    const html = await resp.text();
    document.getElementById('app').innerHTML = html;
    document.getElementById('updated-time').textContent = new Date().toLocaleString('zh-CN', {timeZone: 'UTC'}) + ' UTC';
  } catch (e) {
    document.getElementById('app').innerHTML = '<div class="error">加载失败: ' + e.message + '</div>';
  }
  loading = false;
}

// Auto-refresh every 5 minutes
setInterval(fetchData, 5 * 60 * 1000);
</script>
</body>
</html>
"""

@app.route("/")
def index():
    data = get_data()
    return render_template_string(
        HTML_TEMPLATE,
        format_pct=format_pct,
        color_pct=color_pct,
        **data
    )

@app.route("/api/data")
def api_data():
    """Return only the dashboard content (for AJAX refresh)."""
    data = get_data()
    return render_template_string(
        HTML_TEMPLATE,
        format_pct=format_pct,
        color_pct=color_pct,
        **data
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=False)
