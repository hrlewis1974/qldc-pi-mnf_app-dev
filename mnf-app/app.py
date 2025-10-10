from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from faicons import icon_svg
from shiny import App, Inputs, Outputs, Session, reactive, render, ui
from shinywidgets import output_widget, render_plotly

app_dir = Path(__file__).parent
data_path = app_dir / "data.csv"

# Load data
data_all = pd.read_csv(data_path)
data_all['Date'] = pd.to_datetime(data_all['Date'], format="%d/%m/%Y")
tickers = data_all["Ticker"].unique().tolist() if "Ticker" in data_all.columns else ["LOCAL"]
end = data_all["Date"].max()
start = end - pd.Timedelta(weeks=12)

# --- UI ---
app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_selectize("ticker", "Select DMA", choices=tickers, selected=tickers[0]),
        ui.input_date_range("dates", "Select dates", start=start, end=end),
    ),
    ui.layout_column_wrap(
        ui.value_box(
            "Current Price",
            ui.output_ui("price"),
            showcase=icon_svg("dollar-sign"),
        ),
        ui.value_box(
            "Change",
            ui.output_ui("change"),
            showcase=ui.output_ui("change_icon"),
        ),
        ui.value_box(
            "Percent Change",
            ui.output_ui("change_percent"),
            showcase=icon_svg("percent"),
        ),
        fill=False,
    ),
    ui.layout_columns(
        ui.card(
            ui.card_header("Price history"),
            output_widget("price_history"),
            full_screen=True,
        ),
        ui.card(
            ui.card_header("Latest data"),
            ui.output_data_frame("latest_data"),
        ),
        col_widths=[9, 3],
    ),
    ui.include_css(app_dir / "styles.css"),
    title="Stock explorer (Local CSV)",
    fillable=True,
)

# --- Server logic ---
def server(input: Inputs, output: Outputs, session: Session):
    @reactive.calc
    def get_data():
        dates = input.dates()
        df = data_all.copy()

        # Filter by ticker if column exists
        if "Ticker" in df.columns:
            df = df[df["Ticker"] == input.ticker()]

        # Filter by selected date range
        mask = (df["Date"] >= pd.to_datetime(dates[0])) & (df["Date"] <= pd.to_datetime(dates[1]))
        df = df.loc[mask].sort_values("Date")

        return df

    @reactive.calc
    def get_change():
        close = get_data()["Close"]
        return close.iloc[-1] - close.iloc[-2] if len(close) > 1 else 0

    @reactive.calc
    def get_change_percent():
        close = get_data()["Close"]
        if len(close) > 1:
            change = close.iloc[-1] - close.iloc[-2]
            return change / close.iloc[-2] * 100
        return 0

    @render.ui
    def price():
        close = get_data()["Close"]
        return f"{close.iloc[-1]:.2f}" if not close.empty else "N/A"

    @render.ui
    def change():
        return f"${get_change():.2f}"

    @render.ui
    def change_icon():
        change = get_change()
        icon = icon_svg("arrow-up" if change >= 0 else "arrow-down")
        icon.add_class(f"text-{('success' if change >= 0 else 'danger')}")
        return icon

    @render.ui
    def change_percent():
        return f"{get_change_percent():.2f}%"

    @render_plotly
    def price_history():
        df = get_data().reset_index(drop=True)
        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=df["Date"],
                    open=df["Open"],
                    high=df["High"],
                    low=df["Low"],
                    close=df["Close"],
                    increasing_line_color="#44bb70",
                    decreasing_line_color="#040548",
                    name=input.ticker(),
                )
            ]
        )

        # Add simple moving average
        if len(df) >= 7:
            df["SMA"] = df["Close"].rolling(window=7).mean()
            fig.add_scatter(
                x=df["Date"],
                y=df["SMA"],
                mode="lines",
                name="SMA (7)",
                line={"color": "orange", "dash": "dash"},
            )

        fig.update_layout(
            hovermode="x unified",
            legend={"orientation": "h", "yanchor": "top", "y": 1, "xanchor": "right", "x": 1},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        return fig

    @render.data_frame
    def latest_data():
        df = get_data()
        if df.empty:
            return pd.DataFrame({"Category": [], "Value": []})

        latest = df.iloc[-1:].T.reset_index()
        latest.columns = ["Category", "Value"]
        latest["Value"] = latest["Value"].apply(lambda v: f"{v:.2f}" if isinstance(v, (int, float)) else str(v))
        return latest


app = App(app_ui, server)
