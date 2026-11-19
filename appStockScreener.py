
import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(
    page_title="Stock Screener",
    layout="wide"
)

st.title("Stock Screener")

DEFAULT = "AAPL, MSFT, GOOGL, AMZN, NVDA, JPM, KO, PEP, JNJ, XOM"

raw = st.text_area(
    "Tickers (comma separated). SGX: add .SI, Bursa: add .KL",
    DEFAULT,
)

tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]

# Screening criteria
with st.expander("Screening Criteria", expanded=True):

    col1, col2, col3 = st.columns(3)

    with col1:
        ideal_pe = st.slider("Ideal P/E Below", 5, 40, 25)
        ideal_ps = st.slider("Ideal P/S Below", 0.0, 5.0, 2.2, 0.1)
        ideal_pb = st.slider("Ideal P/B Below", 0.0, 7.0, 3.3, 0.1)
        ideal_peg = st.slider("Ideal PEG Below", 0.0, 3.0, 1.0, 0.1)

    with col2:
        min_growth = st.slider("Minimum Revenue Growth (%)", -20, 50, 5)
        ideal_de = st.slider("Maximum Debt/Equity", 0.0, 1.0, 0.5, 0.1)
        min_div = st.slider("Minimum Dividend Yield (%)", 0.0, 8.0, 0.0, 0.1)

    with col3:
        min_fcf_margin = st.slider(
            "Minimum FCF Margin (%)", -20.0, 100.0, 5.0, 5.0
        )
        above_200 = st.checkbox(
            "Price above 200-day average", value=True
        )


# Fetch financial data
@st.cache_data(ttl=3600)
def load(tickers):

    rows = []

    for t in tickers:

        try:
            info = yf.Ticker(t).info

            price = info.get("currentPrice") or info.get("regularMarketPrice")

            de = info.get("debtToEquity")
            rg = info.get("revenueGrowth")
            fcf = info.get("freeCashflow")
            revenue = info.get("totalRevenue")

            # FCF Margin
            fcf_margin = None

            if fcf is not None and revenue is not None:
                try:
                    fcf = float(fcf)
                    revenue = float(revenue)

                    if revenue > 0:
                        fcf_margin = fcf / revenue * 100

                except (ValueError, TypeError):
                    pass

            # PEG ratio
            peg = info.get("trailingPegRatio")

            if peg is None:
                peg = info.get("pegRatio")

            # Dividend yield
            div_yield = info.get("dividendYield")

            rows.append({

                "Ticker": t,

                "Price": price,

                "P/E": info.get("trailingPE"),

                "P/S": info.get("priceToSalesTrailing12Months"),

                "P/B": info.get("priceToBook"),

                "PEG": peg,

                "Rev Growth %": (
                    rg * 100 if rg is not None else None
                ),

                "D/E": (
                    de / 100 if de is not None else None
                ),

                "Div Yield %": (
                    div_yield * 100
                    if div_yield is not None
                    else None
                ),

                "FCF Margin %": fcf_margin,

                "200d avg": info.get("twoHundredDayAverage"),

            })

        except Exception:
            rows.append({"Ticker": t})

    return pd.DataFrame(rows)


# Run screener
if st.button("Run Screen", type="primary"):

    if not tickers:
        st.warning("Please enter at least one ticker.")

    else:

        with st.spinner("Fetching financial data..."):

            df = load(tuple(tickers))

        if df.empty:
            st.warning("No stock data returned.")
            st.stop()

        # Ensure numeric columns
        numeric_cols = [
            "Price",
            "P/E",
            "P/S",
            "P/B",
            "PEG",
            "Rev Growth %",
            "D/E",
            "Div Yield %",
            "FCF Margin %",
            "200d avg",
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col], errors="coerce"
                )

        # Screening conditions
        def passes(row):

            checks = {

                # Valuation
                "P/E": (
                    pd.notna(row.get("P/E"))
                    and 0 < row["P/E"] <= ideal_pe
                ),

                "P/S": (
                    pd.notna(row.get("P/S"))
                    and 0 < row["P/S"] <= ideal_ps
                ),

                "P/B": (
                    pd.notna(row.get("P/B"))
                    and 0 < row["P/B"] <= ideal_pb
                ),

                "PEG": (
                    pd.notna(row.get("PEG"))
                    and 0 < row["PEG"] <= ideal_peg
                ),

                # Financial quality
                "Growth": (
                    pd.notna(row.get("Rev Growth %"))
                    and row["Rev Growth %"] >= min_growth
                ),

                "D/E": (
                    pd.notna(row.get("D/E"))
                    and row["D/E"] >= 0
                    and row["D/E"] <= ideal_de
                ),

                "Div": (
                    pd.notna(row.get("Div Yield %"))
                    and row["Div Yield %"] >= min_div
                ),

                "FCF Margin": (
                    pd.notna(row.get("FCF Margin %"))
                    and row["FCF Margin %"] >= min_fcf_margin
                ),
            }

            # Technical
            if above_200:
                checks["Trend"] = (
                    pd.notna(row.get("Price"))
                    and pd.notna(row.get("200d avg"))
                    and row["Price"] > row["200d avg"]
                )

            return checks

        # Calculate scores
        results = df.apply(passes, axis=1)

        # Category scores
        df["Valuation"] = results.apply(
            lambda c: sum(
                c[k] for k in ["P/E", "P/S", "P/B", "PEG"]
            )
        )

        df["Quality"] = results.apply(
            lambda c: sum(
                c[k] for k in ["Growth", "D/E", "Div", "FCF Margin"]
            )
        )

        df["Technical"] = results.apply(
            lambda c: int(c.get("Trend", False))
        )

        # Total score
        df["Score"] = (
            df["Valuation"]
            + df["Quality"]
            + df["Technical"]
        )

        df["Max"] = results.apply(len)

        # Sort by score
        df = df.sort_values(
            ["Score", "Quality", "Valuation"],
            ascending=False
        )

        # Display summary
        st.subheader("Screening Results")

        col1, col2, col3 = st.columns(3)

        col1.metric("Stocks Screened", len(df))

        col2.metric(
            "Stocks Passing 6+ Criteria",
            int((df["Score"] >= 6).sum())
        )

        col3.metric(
            "Average Score",
            f"{df['Score'].mean():.1f}/{df['Max'].max()}"
        )

        # Display results
        display_df = df.drop(
            columns=["200d avg"],
            errors="ignore"
        )

        st.dataframe(
            display_df.round(2),
            hide_index=True,
            use_container_width=True
        )

        # Download results
        csv = display_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download Results (CSV)",
            data=csv,
            file_name="stock_screener_results.csv",
            mime="text/csv",
        )

        st.caption(
            "Missing data counts as a fail. Financial data comes "
            "from Yahoo Finance and may be delayed or inaccurate. "
            "PEG definitions may vary between data sources. "
            "This screener is for informational purposes only, "
            "not investment advice."
        )
