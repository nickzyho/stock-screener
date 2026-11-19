
import streamlit as st
import yfinance as yf
import pandas as pd
import time

st.set_page_config(
    page_title="Stock Screener",
    layout="wide"
)

st.title("Stock Screener")

# --------------------------------------------------
# SESSION STATE
# --------------------------------------------------

if "favorites" not in st.session_state:
    st.session_state.favorites = []

if "stock_data" not in st.session_state:
    st.session_state.stock_data = {}

if "last_input_tickers" not in st.session_state:
    st.session_state.last_input_tickers = []

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None


# --------------------------------------------------
# TICKER INPUT
# --------------------------------------------------

raw = st.text_area(
    "Enter stock tickers (comma separated)",
    value="",
    placeholder="Example: AAPL, MSFT, GOOGL, NVDA",
)

tickers = list(dict.fromkeys(
    t.strip().upper()
    for t in raw.split(",")
    if t.strip()
))

# --------------------------------------------------
# SCREENING CRITERIA
# --------------------------------------------------

with st.expander("Screening Criteria", expanded=True):

    col1, col2, col3 = st.columns(3)

    with col1:
        ideal_pe = st.slider(
            "Ideal P/E Below", 5, 40, 25
        )

        ideal_ps = st.slider(
            "Ideal P/S Below", 0.0, 5.0, 2.2, 0.1
        )

        ideal_pb = st.slider(
            "Ideal P/B Below", 0.0, 7.0, 3.3, 0.1
        )

    with col2:
        min_growth = st.slider(
            "Minimum Revenue Growth (%)", -20, 50, 5
        )

        ideal_de = st.slider(
            "Maximum Debt/Equity", 0.0, 1.0, 0.5, 0.1
        )

    with col3:
        min_fcf_margin = st.slider(
            "Minimum FCF Margin (%)", -20.0, 100.0, 5.0, 5.0
        )

        above_200 = st.checkbox(
            "Price above 200-day average", value=True
        )


# --------------------------------------------------
# FETCH ONE STOCK
# --------------------------------------------------

def fetch_stock(t):

    try:
        info = yf.Ticker(t).info

        price = (
            info.get("currentPrice")
            or info.get("regularMarketPrice")
        )

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

        return {
            "Ticker": t,
            "Price": price,
            "P/E": info.get("trailingPE"),
            "P/S": info.get("priceToSalesTrailing12Months"),
            "P/B": info.get("priceToBook"),

            "Rev Growth %": (
                rg * 100 if rg is not None else None
            ),

            "D/E": (
                de / 100 if de is not None else None
            ),

            "FCF Margin %": fcf_margin,

            "200d avg": info.get("twoHundredDayAverage"),

            "Status": (
                "OK" if price is not None
                else "Incomplete Yahoo Finance data"
            ),
        }

    except Exception as e:

        return {
            "Ticker": t,
            "Price": None,
            "P/E": None,
            "P/S": None,
            "P/B": None,
            "Rev Growth %": None,
            "D/E": None,
            "FCF Margin %": None,
            "200d avg": None,
            "Status": str(e),
        }


# --------------------------------------------------
# MANUAL REFRESH
# --------------------------------------------------

st.divider()

if st.button("↻ Refresh Stocks", type="primary"):

    # Always include favourites
    all_tickers = list(dict.fromkeys(
        tickers + st.session_state.favorites
    ))

    if not all_tickers:
        st.warning("Enter some stock tickers or add favourites first.")

    else:

        progress = st.progress(0)

        with st.spinner("Fetching stock data..."):

            total = len(all_tickers)

            for i, t in enumerate(all_tickers):

                new_data = fetch_stock(t)

                # Keep previous data if Yahoo fails temporarily
                if (
                    new_data["Status"] != "OK"
                    and t in st.session_state.stock_data
                    and st.session_state.stock_data[t].get("Price") is not None
                ):
                    old_data = st.session_state.stock_data[t].copy()
                    old_data["Status"] = "Refresh failed - showing previous data"
                    st.session_state.stock_data[t] = old_data

                else:
                    st.session_state.stock_data[t] = new_data

                progress.progress((i + 1) / total)

                # Space out requests
                if i < total - 1:
                    time.sleep(1.5)

        st.session_state.last_input_tickers = tickers.copy()

        st.session_state.last_refresh = time.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        st.success("Stock data refresh completed!")


if st.session_state.last_refresh:
    st.caption(
        f"Last refreshed: {st.session_state.last_refresh}"
    )


# --------------------------------------------------
# SCORING FUNCTION
# --------------------------------------------------

def calculate_scores(data):

    df = pd.DataFrame(data)

    if df.empty:
        return df

    numeric_cols = [
        "Price",
        "P/E",
        "P/S",
        "P/B",
        "Rev Growth %",
        "D/E",
        "FCF Margin %",
        "200d avg",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

    def passes(row):

        checks = {

            # Valuation
            "P/E": (
                pd.notna(row["P/E"])
                and 0 < row["P/E"] <= ideal_pe
            ),

            "P/S": (
                pd.notna(row["P/S"])
                and 0 < row["P/S"] <= ideal_ps
            ),

            "P/B": (
                pd.notna(row["P/B"])
                and 0 < row["P/B"] <= ideal_pb
            ),

            # Financial quality
            "Growth": (
                pd.notna(row["Rev Growth %"])
                and row["Rev Growth %"] >= min_growth
            ),

            "D/E": (
                pd.notna(row["D/E"])
                and 0 <= row["D/E"] <= ideal_de
            ),

            "FCF Margin": (
                pd.notna(row["FCF Margin %"])
                and row["FCF Margin %"] >= min_fcf_margin
            ),
        }

        # Technical
        if above_200:
            checks["Trend"] = (
                pd.notna(row["Price"])
                and pd.notna(row["200d avg"])
                and row["Price"] > row["200d avg"]
            )

        return checks

    results = df.apply(passes, axis=1)

    df["Valuation"] = results.apply(
        lambda c: sum(
            c[k] for k in ["P/E", "P/S", "P/B"]
        )
    )

    df["Quality"] = results.apply(
        lambda c: sum(
            c[k] for k in ["Growth", "D/E", "FCF Margin"]
        )
    )

    df["Technical"] = results.apply(
        lambda c: int(c.get("Trend", False))
    )

    df["Score"] = (
        df["Valuation"]
        + df["Quality"]
        + df["Technical"]
    )

    df["Max"] = results.apply(len)

    return df.sort_values(
        ["Score", "Quality", "Valuation"],
        ascending=False
    )


# --------------------------------------------------
# DISPLAY STOCK TABLE
# --------------------------------------------------

def show_stock_table(symbols, favorite_mode=False):

    data = [
        st.session_state.stock_data[t]
        for t in symbols
        if t in st.session_state.stock_data
    ]

    if not data:
        st.info("No stock data available yet.")
        return

    df = calculate_scores(data)

    st.dataframe(
        df.round(2),
        hide_index=True,
        use_container_width=True
    )

    st.caption(
        "Score = Valuation + Financial Quality + Technical"
    )

    st.markdown("**Manage favourites**")

    for t in df["Ticker"].tolist():

        col1, col2 = st.columns([5, 1])

        col1.write(t)

        if favorite_mode:

            if col2.button(
                "★ Unfavourite",
                key=f"unfav_{t}"
            ):
                st.session_state.favorites.remove(t)
                st.rerun()

        else:

            if col2.button(
                "☆ Favourite",
                key=f"fav_{t}"
            ):
                if t not in st.session_state.favorites:
                    st.session_state.favorites.append(t)

                st.rerun()


# --------------------------------------------------
# SCREENING RESULTS
# --------------------------------------------------

st.divider()

st.subheader("Screening Results")

# Only show entered tickers here.
# Favourited stocks move to the separate section.

active_tickers = [
    t for t in st.session_state.last_input_tickers
    if t not in st.session_state.favorites
]

if active_tickers:

    show_stock_table(active_tickers)

else:

    st.info(
        "Enter stock tickers and click Refresh Stocks. "
        "Favourited stocks are displayed separately below."
    )


# --------------------------------------------------
# FAVOURITES
# --------------------------------------------------

st.divider()

st.subheader("★ My Favourite Stocks")

st.caption(
    "Favourite stocks are automatically included whenever "
    "you manually refresh, even if they are not in the input bar."
)

if st.session_state.favorites:

    show_stock_table(
        st.session_state.favorites,
        favorite_mode=True
    )

else:

    st.info("You haven't added any favourite stocks yet.")


# --------------------------------------------------
# FOOTNOTE
# --------------------------------------------------

st.divider()

st.caption(
    "Financial data from Yahoo Finance. Missing data counts "
    "as a failed screening criterion. Data may be delayed "
    "or inaccurate. This is a screening tool, not investment advice."
)
