import os
from datetime import datetime
import json
import urllib.request

import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px


# =========================
# PAGE SETTINGS
# =========================
st.set_page_config(
    page_title="Market Dashboard",
    page_icon="📊",
    layout="wide"
)


# =========================
# CUSTOM CSS - DARK + RED/GREEN
# =========================
st.markdown("""
<style>
    .stApp {
        background-color: #0b0f14;
        color: #f3f4f6;
    }

    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 96%;
    }

    h1, h2, h3, h4 {
        color: #ffffff;
        font-weight: 700;
    }

    [data-testid="stSidebar"] {
        background-color: #111827;
    }

    .card {
        background: #111827;
        border: 1px solid #1f2937;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 0 0 1px rgba(255,255,255,0.02);
    }

    .green-border {
        border-left: 5px solid #16a34a;
    }

    .red-border {
        border-left: 5px solid #dc2626;
    }

    .label {
        font-size: 0.90rem;
        color: #9ca3af;
        margin-bottom: 3px;
    }

    .big-value {
        font-size: 1.5rem;
        font-weight: 800;
        color: #ffffff;
    }

    .small-note {
        font-size: 0.90rem;
        color: #d1d5db;
        line-height: 1.5;
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)


# =========================
# DATA FOLDER
# =========================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# =========================
# DATA FUNCTIONS
# =========================
def get_file_path(symbol: str, period: str = "1mo", interval: str = "1h") -> str:
    return os.path.join(DATA_DIR, f"{symbol.replace('-', '_').replace('=', '_')}_{period}_{interval}.csv")



def save_data(df: pd.DataFrame, file_path: str):
    df.to_csv(file_path, index=False)



def load_saved_data(file_path: str) -> pd.DataFrame:
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    return pd.DataFrame()



def fetch_data(symbol: str, period: str = "1mo", interval: str = "1h") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval, auto_adjust=True)

    if df.empty:
        return pd.DataFrame()

    df = df.reset_index()

    if "Datetime" not in df.columns:
        if "Date" in df.columns:
            df.rename(columns={"Date": "Datetime"}, inplace=True)

    return df



def get_data(symbol: str, period: str = "1mo", interval: str = "1h") -> pd.DataFrame:
    file_path = get_file_path(symbol, period, interval)

    try:
        df = fetch_data(symbol, period, interval)
        if not df.empty:
            save_data(df, file_path)
            return df
    except Exception:
        pass

    return load_saved_data(file_path)


# =========================
# INDICATORS
# =========================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()

    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df["RSI_14"] = 100 - (100 / (1 + rs))

    df["BB_Middle"] = df["Close"].rolling(20).mean()
    df["BB_STD"] = df["Close"].rolling(20).std()
    df["BB_Upper"] = df["BB_Middle"] + 2 * df["BB_STD"]
    df["BB_Lower"] = df["BB_Middle"] - 2 * df["BB_STD"]

    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    df["Volatility_20"] = df["Close"].rolling(20).std()
    df["Return_%"] = df["Close"].pct_change() * 100

    return df


# =========================
# EXTRA LIVE TABLE
# =========================
def market_watch_table() -> pd.DataFrame:
    watchlist = {
        "BTC-USD": "Bitcoin",
        "ETH-USD": "Ethereum",
        "GC=F": "Gold",
        "SI=F": "Silver",
        "USDTRY=X": "USD/TRY",
        "EURUSD=X": "EUR/USD",
        "AAPL": "Apple",
        "NVDA": "Nvidia"
    }

    rows = []
    for symbol, name in watchlist.items():
        try:
            temp = yf.Ticker(symbol).history(period="2d", interval="1d", auto_adjust=True)
            if temp.empty:
                continue
            latest = float(temp["Close"].iloc[-1])
            prev = float(temp["Close"].iloc[-2]) if len(temp) > 1 else latest
            change_pct = ((latest - prev) / prev) * 100 if prev != 0 else 0
            direction = "▲" if change_pct >= 0 else "▼"
            rows.append({
                "Asset": name,
                "Symbol": symbol,
                "Price": round(latest, 4),
                "Change %": f"{direction} {change_pct:.2f}%"
            })
        except Exception:
            continue

    return pd.DataFrame(rows)



# =========================
# FEAR & GREED INDEX
# =========================
def get_fear_greed_file_path() -> str:
    return os.path.join(DATA_DIR, "fear_greed_index.csv")


def fetch_fear_greed_data(limit: int = 30) -> pd.DataFrame:
    """
    Fetch Crypto Fear & Greed Index data from Alternative.me public API.
    """
    url = f"https://api.alternative.me/fng/?limit={limit}&format=json"

    with urllib.request.urlopen(url, timeout=10) as response:
        raw_data = response.read().decode("utf-8")

    json_data = json.loads(raw_data)
    rows = json_data.get("data", [])

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["value"] = df["value"].astype(int)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
    df = df.rename(columns={
        "value": "Fear_Greed_Value",
        "value_classification": "Classification",
        "timestamp": "Date"
    })

    df = df[["Date", "Fear_Greed_Value", "Classification"]]
    df = df.sort_values("Date").reset_index(drop=True)

    return df


def get_fear_greed_data(limit: int = 30) -> pd.DataFrame:
    """
    First tries to fetch fresh Fear & Greed data.
    If it fails, it loads saved CSV data.
    """
    file_path = get_fear_greed_file_path()

    try:
        df = fetch_fear_greed_data(limit)
        if not df.empty:
            df.to_csv(file_path, index=False)
            return df
    except Exception:
        pass

    if os.path.exists(file_path):
        return pd.read_csv(file_path)

    return pd.DataFrame()


def create_fear_greed_gauge(value: int, classification: str):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": f"Crypto Fear & Greed Index<br><span style='font-size:0.8em;color:gray'>{classification}</span>"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#22c55e" if value >= 50 else "#dc2626"},
            "bgcolor": "#111827",
            "borderwidth": 1,
            "bordercolor": "#374151",
            "steps": [
                {"range": [0, 25], "color": "#7f1d1d"},
                {"range": [25, 45], "color": "#dc2626"},
                {"range": [45, 55], "color": "#6b7280"},
                {"range": [55, 75], "color": "#16a34a"},
                {"range": [75, 100], "color": "#14532d"}
            ],
            "threshold": {
                "line": {"color": "white", "width": 4},
                "thickness": 0.75,
                "value": value
            }
        }
    ))

    fig.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig


def create_fear_greed_line_chart(df: pd.DataFrame):
    colors = ["#16a34a" if value >= 50 else "#dc2626" for value in df["Fear_Greed_Value"]]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["Date"],
        y=df["Fear_Greed_Value"],
        mode="lines+markers",
        name="Fear & Greed",
        line=dict(color="#22c55e", width=2),
        marker=dict(color=colors, size=7)
    ))

    fig.add_hline(y=25, line_dash="dash", line_color="#dc2626", annotation_text="Extreme Fear")
    fig.add_hline(y=50, line_dash="dash", line_color="#6b7280", annotation_text="Neutral")
    fig.add_hline(y=75, line_dash="dash", line_color="#16a34a", annotation_text="Extreme Greed")

    fig.update_layout(
        title="Fear & Greed Index - Last 30 Days",
        template="plotly_dark",
        height=420,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        xaxis_title="Date",
        yaxis_title="Index Value",
        yaxis=dict(range=[0, 100]),
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


def create_fear_greed_pie_chart(df: pd.DataFrame):
    counts = df["Classification"].value_counts().reset_index()
    counts.columns = ["Classification", "Count"]

    color_map = {
        "Extreme Fear": "#7f1d1d",
        "Fear": "#dc2626",
        "Neutral": "#6b7280",
        "Greed": "#16a34a",
        "Extreme Greed": "#14532d"
    }

    fig = px.pie(
        counts,
        names="Classification",
        values="Count",
        hole=0.45,
        color="Classification",
        color_discrete_map=color_map,
        title="Sentiment Distribution"
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


def fear_greed_page():
    st.title("🌍 Crypto Fear & Greed Index")

    st.markdown(
        """
        <div class="card red-border">
            <div class="small-note">
                This section shows the Crypto Fear & Greed Index. It measures crypto market sentiment
                on a 0-100 scale. Low values show fear, high values show greed.
                Data source: Alternative.me Fear & Greed Index API.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    limit = st.sidebar.slider("Fear & Greed History Days", 7, 100, 30)

    if st.sidebar.button("🔄 Refresh Fear & Greed Data"):
        st.session_state["fng_data"] = get_fear_greed_data(limit)

    if "fng_data" not in st.session_state:
        st.session_state["fng_data"] = get_fear_greed_data(limit)

    fng_df = st.session_state["fng_data"]

    if fng_df.empty:
        st.error("Fear & Greed Index data could not be loaded.")
        return

    latest = fng_df.iloc[-1]
    latest_value = int(latest["Fear_Greed_Value"])
    latest_classification = latest["Classification"]
    latest_date = latest["Date"]

    avg_value = fng_df["Fear_Greed_Value"].mean()
    max_value = fng_df["Fear_Greed_Value"].max()
    min_value = fng_df["Fear_Greed_Value"].min()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        border = "green-border" if latest_value >= 50 else "red-border"
        st.markdown(f"""
        <div class="card {border}">
            <div class="label">Current Index</div>
            <div class="big-value">{latest_value}/100</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        border = "green-border" if latest_value >= 50 else "red-border"
        st.markdown(f"""
        <div class="card {border}">
            <div class="label">Sentiment</div>
            <div class="big-value">{latest_classification}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="card green-border">
            <div class="label">Average</div>
            <div class="big-value">{avg_value:.1f}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="card red-border">
            <div class="label">Min / Max</div>
            <div class="big-value">{min_value} / {max_value}</div>
        </div>
        """, unsafe_allow_html=True)

    g1, g2 = st.columns([1.1, 1])
    with g1:
        st.plotly_chart(create_fear_greed_gauge(latest_value, latest_classification), use_container_width=True)

    with g2:
        st.plotly_chart(create_fear_greed_pie_chart(fng_df), use_container_width=True)

    l1, l2 = st.columns([1.6, 1])
    with l1:
        st.plotly_chart(create_fear_greed_line_chart(fng_df), use_container_width=True)

    with l2:
        st.markdown('<div class="section-title">Fear & Greed Data Table</div>', unsafe_allow_html=True)
        table_df = fng_df.copy()
        table_df["Date"] = pd.to_datetime(table_df["Date"]).dt.strftime("%Y-%m-%d")
        st.dataframe(table_df.sort_values("Date", ascending=False), use_container_width=True, hide_index=True)

    st.markdown(
        """
        <div class="card green-border">
            <div class="small-note">
                <b>Interpretation:</b><br>
                0-25 = Extreme Fear, 25-45 = Fear, 45-55 = Neutral,
                55-75 = Greed, 75-100 = Extreme Greed.
                This is not investment advice; it is only a sentiment indicator.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    csv = fng_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Fear & Greed CSV",
        data=csv,
        file_name="fear_greed_index.csv",
        mime="text/csv"
    )


# =========================
# CHARTS
# =========================
def create_price_chart(df: pd.DataFrame, symbol: str):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["Datetime"],
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Price",
        increasing_line_color="#16a34a",
        decreasing_line_color="#dc2626"
    ))

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["SMA_20"],
        mode="lines",
        name="SMA 20",
        line=dict(color="#22c55e", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["EMA_20"],
        mode="lines",
        name="EMA 20",
        line=dict(color="#ef4444", width=2)
    ))

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["BB_Upper"],
        mode="lines",
        name="BB Upper",
        line=dict(color="#f87171", dash="dot")
    ))

    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["BB_Lower"],
        mode="lines",
        name="BB Lower",
        line=dict(color="#4ade80", dash="dot")
    ))

    fig.update_layout(
        title=f"{symbol} Price Chart",
        template="plotly_dark",
        height=520,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig



def create_pie_chart(df: pd.DataFrame):
    bullish = int((df["Close"] >= df["Open"]).sum())
    bearish = int((df["Close"] < df["Open"]).sum())

    pie_df = pd.DataFrame({
        "Type": ["Bullish Hours", "Bearish Hours"],
        "Count": [bullish, bearish]
    })

    fig = px.pie(
        pie_df,
        names="Type",
        values="Count",
        hole=0.45,
        color="Type",
        color_discrete_map={
            "Bullish Hours": "#16a34a",
            "Bearish Hours": "#dc2626"
        }
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        title="Bullish vs Bearish Hours",
        template="plotly_dark",
        height=520,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", y=-0.1)
    )
    return fig



def create_volume_chart(df: pd.DataFrame):
    colors = ["#16a34a" if close >= open_ else "#dc2626" for close, open_ in zip(df["Close"], df["Open"])]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Datetime"],
        y=df["Volume"],
        marker_color=colors,
        name="Volume"
    ))

    fig.update_layout(
        title="Hourly Trading Volume",
        template="plotly_dark",
        height=380,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig



def create_rsi_chart(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["RSI_14"],
        mode="lines",
        name="RSI 14",
        line=dict(color="#22c55e", width=2)
    ))
    fig.add_hline(y=70, line_dash="dash", line_color="#dc2626", annotation_text="Overbought")
    fig.add_hline(y=30, line_dash="dash", line_color="#16a34a", annotation_text="Oversold")
    fig.update_layout(
        title="RSI Indicator",
        template="plotly_dark",
        height=340,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig



def create_macd_chart(df: pd.DataFrame):
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in df["MACD_Hist"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Datetime"],
        y=df["MACD_Hist"],
        name="Histogram",
        marker_color=colors,
        opacity=0.5
    ))
    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["MACD"],
        mode="lines",
        name="MACD",
        line=dict(color="#16a34a", width=2)
    ))
    fig.add_trace(go.Scatter(
        x=df["Datetime"],
        y=df["MACD_Signal"],
        mode="lines",
        name="Signal",
        line=dict(color="#dc2626", width=2)
    ))

    fig.update_layout(
        title="MACD Indicator",
        template="plotly_dark",
        height=340,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig



# =========================
# PENTAGON PIZZA INDEX
# =========================
def get_pizza_index_file_path() -> str:
    return os.path.join(DATA_DIR, "pentagon_pizza_index.csv")


def fetch_pizza_index_data() -> tuple[pd.DataFrame, dict]:
    """
    Fetch visible public text from PizzINT.watch.
    The site does not provide an official public CSV/API in this project,
    so this function reads the public page text and extracts visible status values.
    """
    url = "https://www.pizzint.watch/"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=12) as response:
        html = response.read().decode("utf-8", errors="ignore")

    # Remove very simple tags for text extraction
    import re
    clean = re.sub(r"<script.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<style.*?</style>", " ", clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"<[^>]+>", "\n", clean)
    clean = re.sub(r"\n+", "\n", clean)
    clean = clean.replace("&amp;", "&").replace("&nbsp;", " ").strip()

    doughcon_match = re.search(r"DOUGHCON\s*([1-5])", clean, re.IGNORECASE)
    doughcon = int(doughcon_match.group(1)) if doughcon_match else None

    status_match = re.search(r"STATUS:\s*([A-Z ]+)", clean, re.IGNORECASE)
    status = status_match.group(1).strip() if status_match else "UNKNOWN"

    loc_match = re.search(r"(\d+)\s+LOCATIONS\s+MONITORED", clean, re.IGNORECASE)
    locations_monitored = int(loc_match.group(1)) if loc_match else None

    # Restaurants visible on the public page
    restaurant_names = [
        "DOMINO'S PIZZA",
        "EXTREME PIZZA",
        "DISTRICT PIZZA PALACE",
        "WE, THE PIZZA",
        "PIZZATO PIZZA",
        "PAPA JOHNS PIZZA"
    ]

    rows = []
    for name in restaurant_names:
        pattern = rf"{re.escape(name)}\s*\n\s*([A-Z0-9% ]+)"
        match = re.search(pattern, clean, re.IGNORECASE)
        activity = match.group(1).strip().upper() if match else "UNKNOWN"

        if "SPIKE" in activity:
            score = 95
            level = "SPIKE"
        elif "BUSY" in activity or "INCREASED" in activity:
            score = 75
            level = "BUSY"
        elif "NOMINAL" in activity:
            score = 50
            level = "NOMINAL"
        elif "QUIET" in activity:
            score = 20
            level = "QUIET"
        elif "NO DATA" in activity:
            score = 0
            level = "NO DATA"
        else:
            score = 35
            level = activity

        rows.append({
            "Location": name.title(),
            "Activity": activity,
            "Level": level,
            "Signal Score": score,
            "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    df = pd.DataFrame(rows)

    meta = {
        "Doughcon": doughcon,
        "Status": status,
        "Locations Monitored": locations_monitored,
        "Source": url,
        "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return df, meta


def get_pizza_index_data() -> tuple[pd.DataFrame, dict]:
    file_path = get_pizza_index_file_path()

    try:
        df, meta = fetch_pizza_index_data()
        if not df.empty:
            df.to_csv(file_path, index=False)
            return df, meta
    except Exception:
        pass

    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        meta = {
            "Doughcon": None,
            "Status": "LOADED FROM SAVED CSV",
            "Locations Monitored": len(df),
            "Source": "Saved local CSV",
            "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        return df, meta

    return pd.DataFrame(), {
        "Doughcon": None,
        "Status": "NO DATA",
        "Locations Monitored": 0,
        "Source": "Unavailable",
        "Checked At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def create_pizza_gauge(doughcon):
    # DOUGHCON lower means more serious, so convert to risk score
    if doughcon is None:
        risk_score = 0
        title = "No live DOUGHCON data"
    else:
        risk_score = (6 - int(doughcon)) * 20
        title = f"DOUGHCON {doughcon}"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=risk_score,
        title={"text": f"Pentagon Pizza Index<br><span style='font-size:0.8em;color:gray'>{title}</span>"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "#dc2626" if risk_score >= 60 else "#16a34a"},
            "bgcolor": "#111827",
            "borderwidth": 1,
            "bordercolor": "#374151",
            "steps": [
                {"range": [0, 25], "color": "#14532d"},
                {"range": [25, 50], "color": "#166534"},
                {"range": [50, 75], "color": "#991b1b"},
                {"range": [75, 100], "color": "#7f1d1d"}
            ],
            "threshold": {
                "line": {"color": "white", "width": 4},
                "thickness": 0.75,
                "value": risk_score
            }
        }
    ))

    fig.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=60, b=20)
    )

    return fig


def create_pizza_bar_chart(df: pd.DataFrame):
    colors = ["#dc2626" if score >= 70 else "#16a34a" if score >= 40 else "#6b7280"
              for score in df["Signal Score"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["Location"],
        y=df["Signal Score"],
        marker_color=colors,
        name="Signal Score"
    ))

    fig.update_layout(
        title="Pizza Location Activity Signal",
        template="plotly_dark",
        height=420,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        xaxis_title="Location",
        yaxis_title="Signal Score",
        yaxis=dict(range=[0, 100]),
        margin=dict(l=20, r=20, t=50, b=80)
    )

    return fig


def create_pizza_pie_chart(df: pd.DataFrame):
    counts = df["Level"].value_counts().reset_index()
    counts.columns = ["Level", "Count"]

    color_map = {
        "SPIKE": "#dc2626",
        "BUSY": "#ef4444",
        "NOMINAL": "#16a34a",
        "QUIET": "#6b7280",
        "NO DATA": "#374151"
    }

    fig = px.pie(
        counts,
        names="Level",
        values="Count",
        hole=0.45,
        color="Level",
        color_discrete_map=color_map,
        title="Pizza Signal Distribution"
    )

    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(
        template="plotly_dark",
        height=420,
        paper_bgcolor="#111827",
        plot_bgcolor="#111827",
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


def pizza_index_page():
    st.title("🍕 Pentagon Pizza Index")

    st.markdown(
        """
        <div class="card red-border">
            <div class="small-note">
                This section tracks the public Pentagon Pizza Index idea: unusual pizza-place activity around
                the Pentagon may reflect unusual late-night operational tempo. This is an OSINT-style signal,
                not a proven prediction tool.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.sidebar.button("🔄 Refresh Pizza Index"):
        df, meta = get_pizza_index_data()
        st.session_state["pizza_data"] = df
        st.session_state["pizza_meta"] = meta

    if "pizza_data" not in st.session_state:
        df, meta = get_pizza_index_data()
        st.session_state["pizza_data"] = df
        st.session_state["pizza_meta"] = meta

    pizza_df = st.session_state["pizza_data"]
    meta = st.session_state["pizza_meta"]

    if pizza_df.empty:
        st.error("Pizza Index data could not be loaded.")
        return

    doughcon = meta.get("Doughcon")
    status = meta.get("Status", "UNKNOWN")
    locations = meta.get("Locations Monitored", len(pizza_df))
    checked_at = meta.get("Checked At", "-")

    spike_count = int((pizza_df["Level"] == "SPIKE").sum())
    avg_signal = float(pizza_df["Signal Score"].mean())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        border = "red-border" if doughcon and doughcon <= 3 else "green-border"
        value = f"DOUGHCON {doughcon}" if doughcon else "N/A"
        st.markdown(f"""
        <div class="card {border}">
            <div class="label">Current Level</div>
            <div class="big-value">{value}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="card green-border">
            <div class="label">Status</div>
            <div class="big-value">{status}</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        border = "red-border" if spike_count > 0 else "green-border"
        st.markdown(f"""
        <div class="card {border}">
            <div class="label">Spike Locations</div>
            <div class="big-value">{spike_count}</div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="card red-border">
            <div class="label">Average Signal</div>
            <div class="big-value">{avg_signal:.1f}/100</div>
        </div>
        """, unsafe_allow_html=True)

    top1, top2 = st.columns([1.05, 1])
    with top1:
        st.plotly_chart(create_pizza_gauge(doughcon), use_container_width=True)
    with top2:
        st.plotly_chart(create_pizza_pie_chart(pizza_df), use_container_width=True)

    mid1, mid2 = st.columns([1.5, 1])
    with mid1:
        st.plotly_chart(create_pizza_bar_chart(pizza_df), use_container_width=True)
    with mid2:
        st.markdown('<div class="section-title">Pizza Activity Table</div>', unsafe_allow_html=True)
        st.dataframe(pizza_df, use_container_width=True, hide_index=True)

    st.markdown(
        f"""
        <div class="card green-border">
            <div class="small-note">
                <b>Source:</b> PizzINT.watch public page<br>
                <b>Locations Monitored:</b> {locations}<br>
                <b>Last Checked:</b> {checked_at}<br><br>
                <b>Interpretation:</b> Higher signal scores mean more unusual activity.
                DOUGHCON is shown as a visual risk-style level. This is only an educational OSINT indicator.
                Correlation does not prove causation.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    csv = pizza_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Pizza Index CSV",
        data=csv,
        file_name="pentagon_pizza_index.csv",
        mime="text/csv"
    )


# =========================
# APP
# =========================
def main():
    st.title("📊 Financial Market Dashboard")
    st.markdown(
        """
        <div class="card green-border">
            <div class="small-note">
                This dashboard downloads <b>1-hour (1h)</b> data for the <b>last 1 month</b>, stores it as CSV,
                and explains the market using charts, tables, and technical indicators.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.header("Settings")

    dashboard_section = st.sidebar.radio(
        "Choose Dashboard Section",
        ["Financial Markets", "Fear & Greed Index", "Pentagon Pizza Index"]
    )

    if dashboard_section == "Fear & Greed Index":
        fear_greed_page()
        return

    if dashboard_section == "Pentagon Pizza Index":
        pizza_index_page()
        return

    symbol = st.sidebar.selectbox(
        "Choose Asset",
        ["BTC-USD", "ETH-USD", "AAPL", "MSFT", "TSLA", "NVDA", "GC=F", "USDTRY=X"]
    )

    period = "1mo"
    interval = "1h"

    st.sidebar.write("**Period:** 1 month")
    st.sidebar.write("**Interval:** 1 hour")

    if st.sidebar.button("🔄 Refresh Data"):
        st.session_state["data"] = get_data(symbol, period, interval)
        st.session_state["symbol"] = symbol

    if "data" not in st.session_state or st.session_state.get("symbol") != symbol:
        st.session_state["data"] = get_data(symbol, period, interval)
        st.session_state["symbol"] = symbol

    df = st.session_state["data"]

    if df.empty:
        st.error("Data could not be loaded. Check internet connection or saved CSV files.")
        return

    df = calculate_indicators(df)

    latest_price = float(df["Close"].iloc[-1])
    previous_price = float(df["Close"].iloc[-2]) if len(df) > 1 else latest_price
    hourly_change = latest_price - previous_price
    hourly_change_pct = (hourly_change / previous_price) * 100 if previous_price != 0 else 0

    last_24_close = float(df["Close"].iloc[-24]) if len(df) >= 24 else previous_price
    day_change_pct = ((latest_price - last_24_close) / last_24_close) * 100 if last_24_close != 0 else 0

    highest_price = float(df["High"].max())
    lowest_price = float(df["Low"].min())
    average_volume = float(df["Volume"].mean())
    latest_rsi = float(df["RSI_14"].iloc[-1]) if pd.notna(df["RSI_14"].iloc[-1]) else 0.0

    # Top metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.markdown(f"""
        <div class="card green-border">
            <div class="label">Latest Price</div>
            <div class="big-value">{latest_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        color_class = "green-border" if hourly_change_pct >= 0 else "red-border"
        st.markdown(f"""
        <div class="card {color_class}">
            <div class="label">1H Change</div>
            <div class="big-value">{hourly_change_pct:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        color_class = "green-border" if day_change_pct >= 0 else "red-border"
        st.markdown(f"""
        <div class="card {color_class}">
            <div class="label">24H Change</div>
            <div class="big-value">{day_change_pct:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="card red-border">
            <div class="label">Highest / Lowest</div>
            <div class="big-value">{highest_price:,.2f} / {lowest_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with m5:
        border = "green-border" if latest_rsi < 70 else "red-border"
        st.markdown(f"""
        <div class="card {border}">
            <div class="label">RSI 14</div>
            <div class="big-value">{latest_rsi:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Row 1 - big chart + pie chart
    left, right = st.columns([2.2, 1])
    with left:
        st.plotly_chart(create_price_chart(df, symbol), use_container_width=True)
    with right:
        st.plotly_chart(create_pie_chart(df), use_container_width=True)

    # Row 2 - volume + market watch table
    left2, right2 = st.columns([1.5, 1.2])
    with left2:
        st.plotly_chart(create_volume_chart(df), use_container_width=True)
    with right2:
        st.markdown('<div class="section-title">Live Market Watch</div>', unsafe_allow_html=True)
        watch_df = market_watch_table()
        st.dataframe(watch_df, use_container_width=True, hide_index=True)

        activity_table = pd.DataFrame({
            "Metric": ["Average Volume", "Bullish Hours", "Bearish Hours", "Volatility 20"],
            "Value": [
                round(average_volume, 2),
                int((df["Close"] >= df["Open"]).sum()),
                int((df["Close"] < df["Open"]).sum()),
                round(float(df["Volatility_20"].iloc[-1]) if pd.notna(df["Volatility_20"].iloc[-1]) else 0.0, 4)
            ]
        })
        st.markdown('<div class="section-title">Market Activity Table</div>', unsafe_allow_html=True)
        st.table(activity_table)

    # Row 3 - indicators
    ind1, ind2 = st.columns(2)
    with ind1:
        st.plotly_chart(create_rsi_chart(df), use_container_width=True)
    with ind2:
        st.plotly_chart(create_macd_chart(df), use_container_width=True)

    # Row 4 - explanation + data table
    ex1, ex2 = st.columns([1, 1.7])
    with ex1:
        indicator_table = pd.DataFrame({
            "Indicator": ["SMA 20", "EMA 20", "RSI 14", "Bollinger Bands", "MACD", "Volatility 20"],
            "Explanation": [
                "Average price of the last 20 hours.",
                "Weighted moving average, reacts faster.",
                "Momentum indicator. >70 overbought, <30 oversold.",
                "Shows upper/lower price zones and volatility.",
                "Shows trend direction and momentum changes.",
                "Extra indicator for price instability."
            ]
        })
        st.markdown('<div class="section-title">Technical Indicators Table</div>', unsafe_allow_html=True)
        st.table(indicator_table)

    with ex2:
        st.markdown('<div class="section-title">Stored Hourly Data (Last 100 Rows)</div>', unsafe_allow_html=True)
        st.dataframe(df.tail(100), use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"{symbol}_1month_1hour_data.csv",
            mime="text/csv"
        )

    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
