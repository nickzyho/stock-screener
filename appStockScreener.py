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
    ideal_pe = st.slider("Ideal P/E Lesser Than", 5, 40, 25)
    ideal_ps = st.slider("Ideal P/S Lesser Than", 0.0, 5.0, 2.2, 0.1)
    ideal_pb = st.slider("Ideal P/B Lesser Than", 0.0, 7.0, 3.3, 0.1)
    min_growth = st.slider("Min revenue growth (%)", -20, 50, 5)
    ideal_de = st.slider("Ideal debt/equity (ratio) Lesser Than", 0.0, 1.0, 0.5, 0.1)
    min_div = st.slider("Min dividend yield (%)", 0.0, 8.0, 0.0, 0.1)
    above_200 = st.checkbox("Price above 200-day average", value=True)
    min_fcf_margin = st.slider("Minimum FCF / Sales Revenue (%)", -20.0, 100.0, 5.0, 5.0)
    ideal_peg = st.slider("Ideal PEG Lesser Than", 0.0, 1.0, 0.5, 0.1)


@st.cache_data(ttl=3600)
def load(tickers):
    rows = []
    for t in tickers:
        try:
            info = yf.Ticker(t).info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            div_rate = info.get("dividendRate")
            de = info.get("debtToEquity")
            pb = info.get("priceToBook")
            peg = info.get("trailingPegRatio")
            rg = info.get("revenueGrowth")
            ps = info.get("priceToSalesTrailing12Months")
            fcf = info.get("freeCashflow")
            revenue = info.get("totalRevenue")

            fcf_margin = None

            if fcf is not None and revenue is not None:
                try:
                    fcf = float(fcf)
                    revenue = float(revenue)

                    if revenue > 0:
                        fcf_margin = (fcf / revenue) * 100
                except (ValueError, TypeError):
                    pass

            rows.append({
                "Ticker": t,
                "Price": price,
                "P/E": info.get("trailingPE"),
                "P/S": ps,
                "P/B": pb,
                "Rev growth %": rg * 100 if rg is not None else None,
                "D/E": de / 100 if de is not None else None,
                "Div yield %": (div_rate / price * 100) if div_rate and price else 0.0,
                "200d avg": info.get("twoHundredDayAverage"),
                "FCF Margin %": fcf_margin,
                "PEG": peg,
            })
        except Exception:
            rows.append({"Ticker": t})
    return pd.DataFrame(rows)


if st.button("Run screen", type="primary"):
    with st.spinner("Fetching data..."):
        df = load(tuple(tickers))

    df["FCF Margin %"] = pd.to_numeric(
        df["FCF Margin %"], errors="coerce"
    )

    def passes(row):
        checks = {
            "P/E": pd.notna(row.get("P/E")) and 0 < row["P/E"] <= ideal_pe,
            "Growth": pd.notna(row.get("Rev growth %")) and row["Rev growth %"] >= min_growth,
            "D/E": pd.notna(row.get("D/E")) and row["D/E"] <= ideal_de,
            "Div": pd.notna(row.get("Div yield %")) and row["Div yield %"] >= min_div,
            "P/S": pd.notna(row.get("P/S")) and 0 < row["P/S"] <= ideal_ps,
            "FCF Margin": (
                pd.notna(row.get("FCF Margin %"))
                and row["FCF Margin %"] >= min_fcf_margin
            ),
            "P/B": (
                pd.notna(row.get("P/B"))
                and 0 < row["P/B"] <= ideal_pb
            ),

            "PEG": (
                pd.notna(row.get("PEG"))
                and 0 < row["PEG"] <= ideal_peg
            ),
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

    df = df.drop(columns=["200d avg"]).sort_values(
        "Score", ascending=False
    )

    st.dataframe(df.round(2), hide_index=True, use_container_width=True)
    st.caption(
        "Missing data counts as a fail. Data comes from Yahoo Finance and can "
        "be delayed or wrong. This is a screen, not investment advice."
    )
