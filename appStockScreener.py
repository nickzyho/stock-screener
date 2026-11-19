import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="Stock Screener", layout="centered")
st.title("Stock Screener")

DEFAULT = "AAPL, MSFT, GOOGL, AMZN, NVDA, JPM, KO, PEP, JNJ, XOM"
raw = st.text_area(
    "Tickers (comma separated). SGX: add .SI, Bursa: add .KL",
    DEFAULT,
)
tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]

with st.expander("Criteria", expanded=True):
    max_pe = st.slider("Max P/E", 5, 80, 25)
    min_growth = st.slider("Min revenue growth (%)", -20, 50, 5)
    max_de = st.slider("Max debt/equity (ratio)", 0.0, 5.0, 1.5, 0.1)
    min_div = st.slider("Min dividend yield (%)", 0.0, 8.0, 0.0, 0.1)
    above_200 = st.checkbox("Price above 200-day average", value=True)


@st.cache_data(ttl=3600)
def load(tickers):
    rows = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            div_rate = info.get("dividendRate")
            de = info.get("debtToEquity")
            rg = info.get("revenueGrowth")
            rows.append({
                "Ticker": t,
                "Price": price,
                "P/E": info.get("trailingPE"),
                "Rev growth %": rg * 100 if rg is not None else None,
                "D/E": de / 100 if de is not None else None,
                "Div yield %": (div_rate / price * 100) if div_rate and price else 0.0,
                "200d avg": info.get("twoHundredDayAverage"),
            })
        except Exception:
            rows.append({"Ticker": t})
    return pd.DataFrame(rows)


if st.button("Run screen", type="primary"):
    with st.spinner("Fetching data..."):
        df = load(tuple(tickers))

    def passes(row):
        checks = {
            "P/E": pd.notna(row.get("P/E")) and 0 < row["P/E"] <= max_pe,
            "Growth": pd.notna(row.get("Rev growth %")) and row["Rev growth %"] >= min_growth,
            "D/E": pd.notna(row.get("D/E")) and row["D/E"] <= max_de,
            "Div": pd.notna(row.get("Div yield %")) and row["Div yield %"] >= min_div,
        }
        if above_200:
            checks["Trend"] = (
                pd.notna(row.get("Price"))
                and pd.notna(row.get("200d avg"))
                and row["Price"] > row["200d avg"]
            )
        return checks

    results = df.apply(passes, axis=1)
    df["Score"] = results.apply(lambda c: sum(c.values()))
    df["Max"] = results.apply(len)
    df = df.drop(columns=["200d avg"]).sort_values("Score", ascending=False)

    st.dataframe(df.round(2), hide_index=True, use_container_width=True)
    st.caption(
        "Missing data counts as a fail. Data comes from Yahoo Finance and can "
        "be delayed or wrong. This is a screen, not investment advice."
    )
