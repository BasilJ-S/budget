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
    yaxis=dict(
        gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)", tickprefix="$"
    ),
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
            dbc.Col(
                [
                    html.H2("Budget Dashboard", className="mb-0 fw-bold"),
                    html.P(
                        "Personal Finance Overview", className="text-muted mt-1 mb-0"
                    ),
                ]
            ),
            className="mb-4 mt-2",
        ),
        # Month control
        dbc.Row(
            dbc.Col(
                [
                    html.Label("Month", style=LABEL_STYLE),
                    dcc.Dropdown(
                        id="month-dropdown",
                        options=[
                            {"label": fmt_month(m), "value": m} for m in all_months
                        ],
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
            className="mb-3 g-3",
        ),
        dbc.Row(
            id="income-kpi-row",
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
        # Month-over-Month Spending Change
        dbc.Row(
            dbc.Col(
                dbc.Card(
                    [
                        dbc.CardHeader("Month-over-Month Spending Change"),
                        dbc.CardBody(dcc.Graph(id="mom-change-chart")),
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
        # Day-of-week + compliance side by side
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Avg Daily Spending by Day of Week"),
                            dbc.CardBody(dcc.Graph(id="dow-heatmap-chart")),
                        ],
                        className="mb-4 shadow-sm",
                    ),
                    md=6,
                ),
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader("Budget Compliance History"),
                            dbc.CardBody(dcc.Graph(id="compliance-heatmap-chart")),
                        ],
                        className="mb-4 shadow-sm",
                    ),
                    md=6,
                ),
            ]
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
            dbc.CardBody(
                [
                    html.P(label, style={**LABEL_STYLE, "marginBottom": "6px"}),
                    html.H4(value, className="mb-0 fw-bold", style={"color": color}),
                ]
            ),
            className="shadow-sm h-100",
            style={"borderTop": f"3px solid {color}"},
        ),
        md=3,
        xs=6,
    )


@app.callback(
    Output("kpi-row", "children"),
    Output("income-kpi-row", "children"),
    Output("monthly-bar-chart", "figure"),
    Output("monthly-line-chart", "figure"),
    Output("monthly-summary-table", "children"),
    Output("monthly-category-chart", "figure"),
    Output("monthly-budget-chart", "figure"),
    Output("mom-change-chart", "figure"),
    Output("cumulative-line-chart", "figure"),
    Output("dow-heatmap-chart", "figure"),
    Output("compliance-heatmap-chart", "figure"),
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

    budget = read_budget("Soma")

    # --- KPI Cards ---
    m_in = monthly_summary.loc[selected_month, "total_in"]
    m_out = monthly_summary.loc[selected_month, "total_out"]
    m_net = m_in - m_out
    # Month-over-month net change
    all_month_list = sorted(monthly_summary.index.tolist())
    prev_idx = all_month_list.index(selected_month) - 1
    prev_month = all_month_list[prev_idx] if prev_idx >= 0 else None
    if prev_month is not None:
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
        None,  # placeholder — budget card added after evaluate_budget
        None,  # placeholder — budget remaining card added after evaluate_budget
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
    logger.info(f"Budget: {budget}")

    budget_data = evaluate_budget(
        budget, selected_month_categorical_in_out, "total_in", "total_out"
    )

    logger.info(f"BUDGET: {budget_data}")

    budget_data = budget_data.sort_values(by=["Type", "Value"], ascending=[True, False])

    # Budget KPIs: only count expense items (income items like salary are excluded)
    expense_data = budget_data[budget_data["ItemType"] == "expense"]
    expense_budgeted = expense_data.loc[expense_data["Type"] == "budgeted", "Value"].sum()
    expense_actual = expense_data.loc[expense_data["Type"] == "actual", "Value"].sum()
    budget_remaining = expense_budgeted - expense_actual
    kpi_cards[2] = _kpi_card("Budget", f"${expense_budgeted:,.2f}", "#2c3e50")
    kpi_cards[3] = _kpi_card(
        "Budget Remaining",
        f"${budget_remaining:,.2f}",
        "#18bc9c" if budget_remaining >= 0 else "#e74c3c",
    )

    # Income KPIs: income, expenses, net, savings rate
    income_data = budget_data[budget_data["ItemType"] == "income"]
    income_actual = income_data.loc[income_data["Type"] == "actual", "Value"].sum()
    # income actuals are out - in, so actual income is the negative
    actual_income = -income_actual
    actual_net = actual_income - expense_actual
    savings_rate = (actual_income - expense_actual) / actual_income * 100 if actual_income > 0 else 0
    income_kpi_cards = [
        _kpi_card("Income", f"${actual_income:,.2f}", "#18bc9c"),
        _kpi_card("Expenses", f"${expense_actual:,.2f}", "#e74c3c"),
        _kpi_card(
            "Net",
            f"${actual_net:,.2f}",
            "#18bc9c" if actual_net >= 0 else "#e74c3c",
        ),
        _kpi_card(
            "Savings Rate",
            f"{savings_rate:.1f}%",
            "#18bc9c" if savings_rate >= 0 else "#e74c3c",
        ),
    ]

    # Exclude income items from the budget vs actuals chart
    budget_data = budget_data[budget_data["ItemType"] == "expense"]

    # Build per-category hover detail for the Unbudgeted bar
    budgeted_cat_set = {cat for item in budget.items for cat in item.categories}
    unbudgeted_rows = selected_month_categorical_in_out[
        ~selected_month_categorical_in_out["category"].isin(budgeted_cat_set)
    ].copy()
    unbudgeted_rows["net"] = unbudgeted_rows["total_out"] - unbudgeted_rows["total_in"]
    unbudgeted_rows = unbudgeted_rows.sort_values("net", ascending=False)
    unbudgeted_detail = "".join(
        f"<br>  {r['category']}: ${r['net']:,.2f}"
        for _, r in unbudgeted_rows.iterrows()
    )
    budget_data["hover_extra"] = budget_data["Category"].apply(
        lambda c: unbudgeted_detail if c == "Unbudgeted" else ""
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
        custom_data=["hover_extra"],
    )
    budget_bar_fig.update_traces(
        textposition="outside",
        marker_line_width=0,
        hovertemplate="<b>%{x}</b> — %{fullData.name}<br>$%{y:,.2f}%{customdata[0]}<extra></extra>",
    )
    budget_bar_fig.update_layout(**CHART_LAYOUT)

    start_month = str(pd.Period(selected_month, freq="M") - (num_months - 1))

    # --- Line Chart of In/Out ---
    if not selected_category:
        selected_category = ["All"]
    elif isinstance(selected_category, str):
        selected_category = [selected_category]

    prev_months = category_monthly[
        (category_monthly["month"] >= start_month)
        & (category_monthly["month"] <= selected_month)
    ]

    line_figure = go.Figure()

    color_palette = px.colors.qualitative.Plotly
    color_cycle = itertools.cycle(color_palette)
    category_colors = {cat: next(color_cycle) for cat in selected_category}

    window_months = pd.period_range(
        start=start_month, end=selected_month, freq="M"
    ).astype(str)
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
        yaxis=dict(
            gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)", tickprefix="$"
        ),
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

    # --- Month-over-Month Change by Category ---
    if prev_month is not None:
        curr_cat = selected_month_categorical_in_out[["category", "total_out"]].rename(
            columns={"total_out": "curr_out"}
        )
        prev_cat = category_monthly[category_monthly["month"] == prev_month][
            ["category", "total_out"]
        ].rename(columns={"total_out": "prev_out"})
        mom_cat = curr_cat.merge(prev_cat, on="category", how="outer").fillna(0)
        mom_cat["pct_change"] = (
            (mom_cat["curr_out"] - mom_cat["prev_out"])
            / mom_cat["prev_out"].replace(0, float("nan"))
            * 100
        )
        mom_cat = mom_cat.dropna(subset=["pct_change"])
        if "All" not in selected_category:
            mom_cat = mom_cat[mom_cat["category"].isin(selected_category)]
        mom_cat = mom_cat.sort_values("pct_change")
        mom_fig = go.Figure(
            go.Bar(
                x=mom_cat["category"],
                y=mom_cat["pct_change"],
                marker_color=[
                    "#e74c3c" if v > 0 else "#18bc9c" for v in mom_cat["pct_change"]
                ],
                marker_line_width=0,
                text=[f"{v:+.1f}%" for v in mom_cat["pct_change"]],
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
            )
        )
        mom_fig.update_layout(
            xaxis_title="Category",
            yaxis_title="% Change",
            showlegend=False,
            xaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)"),
            yaxis=dict(
                ticksuffix="%",
                gridcolor="rgba(0,0,0,0.06)",
                linecolor="rgba(0,0,0,0.1)",
                zeroline=True,
                zerolinecolor="rgba(0,0,0,0.2)",
                zerolinewidth=1,
            ),
            **{k: v for k, v in CHART_LAYOUT.items() if k not in ("xaxis", "yaxis")},
        )
    else:
        mom_fig = go.Figure()
        mom_fig.add_annotation(
            text="No prior month available",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color="#6c757d"),
        )
        mom_fig.update_layout(**CHART_LAYOUT)

    # --- Day-of-Week Spending Heatmap ---
    window_tx = transactions_df[
        (transactions_df["month"] >= start_month)
        & (transactions_df["month"] <= selected_month)
    ].copy()
    cats_to_show = (
        all_categories.tolist() if "All" in selected_category else selected_category
    )
    dow_tx = window_tx[window_tx["category"].isin(cats_to_show)].copy()
    dow_tx["day_of_week"] = dow_tx["date"].dt.day_name()
    daily_cat = dow_tx.groupby(["date", "category"])["money_out"].sum().reset_index()
    daily_cat["day_of_week"] = pd.to_datetime(daily_cat["date"]).dt.day_name()
    dow_avg = (
        daily_cat.groupby(["category", "day_of_week"])["money_out"].mean().reset_index()
    )
    day_order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    dow_pivot = dow_avg.pivot(
        index="category", columns="day_of_week", values="money_out"
    ).fillna(0)
    dow_pivot = dow_pivot.reindex(
        columns=[d for d in day_order if d in dow_pivot.columns]
    )
    dow_heatmap_fig = go.Figure(
        go.Heatmap(
            z=dow_pivot.values.tolist(),
            x=[d[:3] for d in dow_pivot.columns.tolist()],
            y=dow_pivot.index.tolist(),
            colorscale=[[0, "#fff5f5"], [1, "#e74c3c"]],
            text=[[f"${v:.0f}" for v in row] for row in dow_pivot.values],
            texttemplate="%{text}",
            showscale=False,
            hovertemplate="<b>%{y}</b><br>%{x}: $%{z:.2f} avg<extra></extra>",
        )
    )
    dow_heatmap_fig.update_layout(
        xaxis_title="Day of Week",
        xaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)"),
        yaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)"),
        **{k: v for k, v in CHART_LAYOUT.items() if k not in ("xaxis", "yaxis")},
    )

    # --- Budget Compliance History ---
    compliance_records = []
    for m in window_months:
        m_cat = category_monthly[category_monthly["month"] == m]
        if m_cat.empty:
            continue
        try:
            b_data = evaluate_budget(budget, m_cat, "total_in", "total_out")
            b_data = b_data[b_data["ItemType"] == "expense"]
            budgeted = b_data[b_data["Type"] == "budgeted"].set_index("Category")[
                "Value"
            ]
            actual_vals = b_data[b_data["Type"] == "actual"].set_index("Category")[
                "Value"
            ]
            for cat in budgeted.index:
                bval = float(budgeted[cat])
                aval = float(actual_vals.get(cat, 0))
                pct = ((aval - bval) / bval * 100) if bval != 0 else 0
                compliance_records.append(
                    {"month": fmt_month(m), "category": cat, "pct": pct}
                )
        except Exception:
            continue

    if compliance_records:
        compliance_df = pd.DataFrame(compliance_records)
        if "All" not in selected_category:
            compliance_df = compliance_df[
                compliance_df["category"].apply(
                    lambda c: any(sc in c for sc in selected_category)
                )
            ]
        if not compliance_df.empty:
            comp_pivot = compliance_df.pivot_table(
                index="category", columns="month", values="pct", aggfunc="first"
            ).fillna(0)
            ordered_labels = [fmt_month(m) for m in window_months]
            comp_pivot = comp_pivot.reindex(
                columns=[l for l in ordered_labels if l in comp_pivot.columns]
            )
            compliance_heatmap_fig = go.Figure(
                go.Heatmap(
                    z=comp_pivot.values.tolist(),
                    x=comp_pivot.columns.tolist(),
                    y=comp_pivot.index.tolist(),
                    colorscale=[[0.0, "#18bc9c"], [0.5, "#f8f9fa"], [1.0, "#e74c3c"]],
                    zmid=0,
                    text=[[f"{v:+.0f}%" for v in row] for row in comp_pivot.values],
                    texttemplate="%{text}",
                    colorbar=dict(title="% vs Budget", ticksuffix="%"),
                    hovertemplate="<b>%{y}</b><br>%{x}: %{text}<extra></extra>",
                )
            )
            compliance_heatmap_fig.update_layout(
                xaxis=dict(
                    type="category",
                    categoryorder="array",
                    categoryarray=ordered_labels,
                    gridcolor="rgba(0,0,0,0.06)",
                    linecolor="rgba(0,0,0,0.1)",
                ),
                yaxis=dict(gridcolor="rgba(0,0,0,0.06)", linecolor="rgba(0,0,0,0.1)"),
                **{
                    k: v for k, v in CHART_LAYOUT.items() if k not in ("xaxis", "yaxis")
                },
            )
        else:
            compliance_heatmap_fig = go.Figure()
            compliance_heatmap_fig.update_layout(**CHART_LAYOUT)
    else:
        compliance_heatmap_fig = go.Figure()
        compliance_heatmap_fig.update_layout(**CHART_LAYOUT)

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
            {
                "if": {"state": "selected"},
                "backgroundColor": "#e8f5f2",
                "border": "none",
            },
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
        income_kpi_cards,
        figure,
        line_figure,
        table,
        category_figure,
        budget_bar_fig,
        mom_fig,
        cumulative_line_figure,
        dow_heatmap_fig,
        compliance_heatmap_fig,
    )


if __name__ == "__main__":
    app.run(debug=True)
