import itertools
import logging

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output

from budget.budget_manager import evaluate_budget, read_budget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
)
logger = logging.getLogger(__name__)

pio.templates.default = "plotly_white"

# -- Data Preparation --

# Read the transactions CSV
transactions_df = pd.read_csv("src/budget/data/transactions.csv")
transactions_df["date"] = pd.to_datetime(transactions_df["date"])

# Make sure 'in' and 'out' columns exist
# Rename for clarity
transactions_df = transactions_df.rename(columns={"in": "money_in", "out": "money_out"})

# Add month column
transactions_df["month"] = transactions_df["date"].dt.to_period("M").astype(str)

all_months = pd.period_range(
    start=transactions_df["month"].min(), end=transactions_df["month"].max(), freq="M"
).astype(str)

all_categories = transactions_df["category"].dropna().unique()


def fmt_month(period_str: str) -> str:
    """Convert '2024-01' to 'Jan 2024'."""
    return pd.Period(period_str, freq="M").strftime("%b %Y")

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", size=13),
    margin=dict(l=40, r=20, t=48, b=40),
    legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
    xaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)"),
    yaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)", tickprefix="$"),
)

LABEL_STYLE = {
    "fontSize": "0.75rem",
    "textTransform": "uppercase",
    "letterSpacing": "0.06em",
    "color": "#6c757d",
    "marginBottom": "4px",
}

# --- Dash App ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.FLATLY])

app.layout = dbc.Container(
    fluid=True,
    className="px-4 py-3",
    children=[
        # Header
        dbc.Row(
            dbc.Col([
                html.H2("Budget Dashboard", className="mb-0 fw-bold"),
                html.P("Personal Finance Overview", className="text-muted mt-1 mb-0"),
            ]),
            className="mb-4 mt-2",
        ),

        # Month control
        dbc.Row(
            dbc.Col(
                [
                    html.Label("Month", style=LABEL_STYLE),
                    dcc.Dropdown(
                        id="month-dropdown",
                        options=[{"label": fmt_month(m), "value": m} for m in all_months],
                        value=all_months[-1],
                        clearable=False,
                    ),
                ],
                md=3,
            ),
            className="mb-4",
        ),

        # KPI summary cards
        dbc.Row(
            id="kpi-row",
            className="mb-4 g-3",
        ),

        # Monthly snapshot — two side-by-side charts
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Monthly In / Out"),
                            dbc.CardBody(dcc.Graph(id="monthly-bar-chart")),
                        ],
                        className="mb-4 shadow-sm",
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Spending by Category"),
                            dbc.CardBody(dcc.Graph(id="monthly-category-chart")),
                        ],
                        className="mb-4 shadow-sm",
                    ),
                    md=6,
                ),
            ]
        ),

        # Budget vs Actuals
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Budget vs Actuals"),
                        dbc.CardBody(dcc.Graph(id="monthly-budget-chart")),
                    ],
                    className="mb-4 shadow-sm",
                )
            )
        ),

        # Trends controls — apply to both charts below
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Look-back Months", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="num-months-dropdown",
                            options=[
                                {"label": m, "value": m}
                                for m in range(1, len(all_months) + 1)
                            ],
                            value=6,
                            clearable=False,
                        ),
                    ],
                    md=2,
                ),
                dbc.Col(
                    [
                        html.Label("Category Filter", style=LABEL_STYLE),
                        dcc.Dropdown(
                            id="category-dropdown",
                            options=[
                                {"label": "All", "value": "All"},
                                *(
                                    {"label": str(cat), "value": str(cat)}
                                    for cat in all_categories
                                ),
                            ],
                            value="All",
                            clearable=True,
                            multi=True,
                        ),
                    ],
                    md=5,
                ),
            ],
            className="mb-3 align-items-end",
        ),

        # Trends
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Monthly Trends by Category"),
                        dbc.CardBody(dcc.Graph(id="monthly-line-chart")),
                    ],
                    className="mb-4 shadow-sm",
                )
            )
        ),

        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Cumulative Net Position"),
                        dbc.CardBody(dcc.Graph(id="cumulative-line-chart")),
                    ],
                    className="mb-4 shadow-sm",
                )
            )
        ),

        # Transactions table
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Monthly Transactions"),
                        dbc.CardBody(html.Div(id="monthly-summary-table")),
                    ],
                    className="mb-4 shadow-sm",
                )
            )
        ),
    ],
)


def _kpi_card(label: str, value: str, color: str = "#2c3e50") -> dbc.Col:
    return dbc.Col(
        dbc.Card(
            dbc.CardBody([
                html.P(label, style={**LABEL_STYLE, "marginBottom": "6px"}),
                html.H4(value, className="mb-0 fw-bold", style={"color": color}),
            ]),
            className="shadow-sm h-100",
            style={"borderTop": f"3px solid {color}"},
        ),
        md=3, xs=6,
    )


@app.callback(
    Output("kpi-row", "children"),
    Output("monthly-bar-chart", "figure"),
    Output("monthly-line-chart", "figure"),
    Output("monthly-summary-table", "children"),
    Output("monthly-category-chart", "figure"),
    Output("monthly-budget-chart", "figure"),
    Output("cumulative-line-chart", "figure"),
    Input("month-dropdown", "value"),
    Input("num-months-dropdown", "value"),
    Input("category-dropdown", "value"),
)
def update_chart(selected_month, num_months, selected_category):

    # Aggregate monthly sums
    monthly_summary = transactions_df.groupby("month").agg(
        total_in=pd.NamedAgg(column="money_in", aggfunc="sum"),
        total_out=pd.NamedAgg(column="money_out", aggfunc="sum"),
    )
    monthly_summary = monthly_summary.reset_index().set_index("month")
    logger.info(f"Monthly Summary: {monthly_summary}")

    # --- KPI Cards ---
    m_in = monthly_summary.loc[selected_month, "total_in"]
    m_out = monthly_summary.loc[selected_month, "total_out"]
    m_net = m_in - m_out
    # Month-over-month net change
    all_month_list = sorted(monthly_summary.index.tolist())
    prev_idx = all_month_list.index(selected_month) - 1
    if prev_idx >= 0:
        prev_month = all_month_list[prev_idx]
        prev_out = monthly_summary.loc[prev_month, "total_out"]
        mom_delta = m_out - prev_out
        mom_sign = "+" if mom_delta >= 0 else ""
        mom_label = f"{mom_sign}${mom_delta:,.0f} vs {fmt_month(prev_month)}"
        mom_color = "#e74c3c" if mom_delta > 0 else "#18bc9c"
    else:
        mom_label = "No prior month"
        mom_color = "#6c757d"

    kpi_cards = [
        _kpi_card("Money In", f"${m_in:,.2f}", "#18bc9c"),
        _kpi_card("Money Out", f"${m_out:,.2f}", "#e74c3c"),
        _kpi_card("Net", f"${m_net:,.2f}", "#18bc9c" if m_net >= 0 else "#e74c3c"),
        _kpi_card("Spending vs Prior Month", mom_label, mom_color),
    ]

    # --- Total In Out Bar Chart ---

    data = pd.DataFrame(
        {
            "Type": ["Money In", "Money Out"],
            "Amount": [m_in, m_out],
        }
    )
    figure = px.bar(
        data,
        x="Type",
        y="Amount",
        labels={"Type": "", "Amount": "Amount ($)"},
        text=data["Amount"].apply(lambda v: f"${v:,.2f}"),
        color="Type",
        color_discrete_map={"Money In": "#18bc9c", "Money Out": "#e74c3c"},
    )
    figure.update_traces(textposition="outside", marker_line_width=0)
    figure.update_layout(**CHART_LAYOUT, showlegend=False)
    logger.info(f"Overall Sum: {data['Amount'].sum()}")

    # --- Categorical In Out Bar Chart ---

    # Aggregate by category and month for line plot
    category_monthly = (
        transactions_df.groupby(["month", "category"])
        .agg(
            total_in=pd.NamedAgg(column="money_in", aggfunc="sum"),
            total_out=pd.NamedAgg(column="money_out", aggfunc="sum"),
        )
        .reset_index()
    )
    selected_month_categorical_in_out = category_monthly[
        category_monthly["month"] == selected_month
    ]

    selected_month_categorical_in_out = selected_month_categorical_in_out.sort_values(
        by="total_out", ascending=False
    )

    category_figure = px.bar(
        selected_month_categorical_in_out,
        x="category",
        y=["total_in", "total_out"],
        barmode="group",
        labels={"value": "Amount ($)", "category": "Category", "variable": ""},
        color_discrete_map={"total_in": "#18bc9c", "total_out": "#e74c3c"},
    )
    category_figure.for_each_trace(
        lambda t: t.update(name="In" if t.name == "total_in" else "Out")
    )
    category_figure.update_traces(marker_line_width=0)
    category_figure.update_layout(**CHART_LAYOUT)

    # --- Budget vs Actuals ---
    budget = read_budget("Student")
    logger.info(f"Budget: {budget}")

    budget_data = evaluate_budget(
        budget, selected_month_categorical_in_out, "total_in", "total_out"
    )

    logger.info(f"BUDGET: {budget_data}")

    budget_data = budget_data.sort_values(by=["Type", "Value"], ascending=[True, False])
    logger.info(
        f"Budget Sum: {budget_data[budget_data['Type'] == 'actual']['Value'].sum()}"
    )

    budget_bar_fig = px.bar(
        budget_data,
        x="Category",
        y="Value",
        color="Type",
        barmode="group",
        labels={"Value": "Amount ($)", "Category": "Category", "Type": ""},
        text=budget_data["Value"].apply(lambda v: f"${v:,.2f}"),
        color_discrete_map={"budget": "#95a5a6", "actual": "#e74c3c"},
    )
    budget_bar_fig.update_traces(textposition="outside", marker_line_width=0)
    budget_bar_fig.update_layout(**CHART_LAYOUT)

    start_month = str(pd.Period(selected_month, freq="M") - (num_months - 1))

    # --- Line Chart of In/Out ---
    if isinstance(selected_category, str):
        selected_category = [selected_category]

    prev_months = category_monthly[
        (category_monthly["month"] >= start_month)
        & (category_monthly["month"] <= selected_month)
    ]

    line_figure = go.Figure()

    color_palette = px.colors.qualitative.Plotly
    color_cycle = itertools.cycle(color_palette)
    category_colors = {cat: next(color_cycle) for cat in selected_category}

    window_months = pd.period_range(start=start_month, end=selected_month, freq="M").astype(str)
    window_labels = [fmt_month(m) for m in window_months]

    for cat in selected_category:
        if cat == "All":
            cat_data = (
                prev_months.groupby("month")
                .agg(
                    total_in=pd.NamedAgg(column="total_in", aggfunc="sum"),
                    total_out=pd.NamedAgg(column="total_out", aggfunc="sum"),
                )
                .reset_index()
            )
        else:
            cat_data = prev_months[prev_months["category"] == cat]
        logger.info(f"Category Data for {cat}: {cat_data}")
        # Fill missing months with 0 and use formatted labels
        cat_data = (
            cat_data.set_index("month")
            .reindex(window_months, fill_value=0)
            .reset_index()
            .rename(columns={"index": "month"})
        )
        cat_data["month_label"] = [fmt_month(m) for m in cat_data["month"]]
        # Money In: dashed line
        line_figure.add_trace(
            go.Scatter(
                x=cat_data["month_label"],
                y=cat_data["total_in"],
                mode="lines+markers",
                name=f"{cat} In",
                line=dict(color=category_colors[cat], dash="dash"),
                marker=dict(size=5),
            )
        )
        # Money Out: solid line
        line_figure.add_trace(
            go.Scatter(
                x=cat_data["month_label"],
                y=cat_data["total_out"],
                mode="lines+markers",
                name=f"{cat} Out",
                line=dict(color=category_colors[cat], dash="solid"),
                marker=dict(size=5),
            )
        )

    line_figure.update_layout(
        xaxis_title="Month",
        yaxis_title="Amount ($)",
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=window_labels,
            gridcolor="rgba(0,0,0,0.06)",
            linecolor="rgba(0,0,0,0.1)",
        ),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)", tickprefix="$"),
        **{k: v for k, v in CHART_LAYOUT.items() if k not in ("xaxis", "yaxis")},
    )

    # --- Cumulative Line Chart ---

    daily_transactions = (
        transactions_df.copy()
        .groupby("date")
        .agg(
            total_in=pd.NamedAgg(column="money_in", aggfunc="sum"),
            total_out=pd.NamedAgg(column="money_out", aggfunc="sum"),
        )
        .reset_index()
    )
    end_date = pd.Period(selected_month, freq="M").end_time
    daily_transactions["net"] = (
        daily_transactions["total_in"] - daily_transactions["total_out"]
    )

    daily_cumulative = daily_transactions.sort_values(by="date").copy()
    daily_cumulative["cumulative"] = daily_cumulative["net"].cumsum()
    daily_cumulative["cumulative_rolling_avg"] = (
        daily_cumulative["cumulative"].rolling(window=20, center=True).mean()
    )
    daily_cumulative = daily_cumulative[
        (daily_cumulative["date"] >= pd.to_datetime(start_month + "-01"))
        & (daily_cumulative["date"] <= end_date)
    ]

    cumulative_line_figure = px.line(
        daily_cumulative,
        x="date",
        y=["cumulative", "cumulative_rolling_avg"],
        labels={"value": "Amount ($)", "date": "Date", "variable": ""},
        color_discrete_map={
            "cumulative": "#2c3e50",
            "cumulative_rolling_avg": "rgba(44,62,80,0.35)",
        },
    )
    cumulative_line_figure.for_each_trace(
        lambda t: t.update(
            name="Net Position" if t.name == "cumulative" else "20-day Average"
        )
    )
    cumulative_line_figure.update_layout(**CHART_LAYOUT)

    # --- Monthly Summary Table ---

    monthly_transactions = transactions_df[
        transactions_df["month"] == selected_month
    ].copy()
    # Format columns for display

    monthly_transactions["date"] = pd.to_datetime(
        monthly_transactions["date"]
    ).dt.strftime("%Y-%m-%d")

    # Table
    table = dash_table.DataTable(
        columns=[
            {"name": "Date", "id": "date"},
            {"name": "Description", "id": "description"},
            {"name": "Category", "id": "category"},
            {"name": "Money In", "id": "money_in"},
            {"name": "Money Out", "id": "money_out"},
        ],
        data=monthly_transactions.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_header={
            "backgroundColor": "#f8f9fa",
            "fontWeight": "600",
            "fontSize": "0.78rem",
            "textTransform": "uppercase",
            "letterSpacing": "0.06em",
            "border": "none",
            "borderBottom": "2px solid #dee2e6",
            "color": "#6c757d",
        },
        style_cell={
            "backgroundColor": "white",
            "textAlign": "left",
            "fontSize": "0.875rem",
            "padding": "10px 14px",
            "border": "none",
            "borderBottom": "1px solid #f0f0f0",
            "fontFamily": "Inter, system-ui, sans-serif",
        },
        style_data_conditional=[
            {"if": {"filter_query": "{money_in} > 0"}, "color": "#18bc9c"},
            {"if": {"filter_query": "{money_out} > 0"}, "color": "#e74c3c"},
            {"if": {"state": "selected"}, "backgroundColor": "#e8f5f2", "border": "none"},
        ],
        style_filter={
            "backgroundColor": "#fafafa",
            "border": "none",
            "borderBottom": "1px solid #e9ecef",
        },
        sort_action="native",
        filter_action="native",
    )
    logger.info("Update complete")

    return (
        kpi_cards,
        figure,
        line_figure,
        table,
        category_figure,
        budget_bar_fig,
        cumulative_line_figure,
    )


if __name__ == "__main__":
    app.run(debug=True)
