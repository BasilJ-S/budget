import itertools
import logging

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table, dcc, html
from dash.dependencies import Input, Output

from budget.budget_manager import evaluate_budget, read_budget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -- Data Preparation --

# Read the transactions CSV
transactions_df = pd.read_csv("src/budget/data/transactions.csv")
transactions_df["date"] = pd.to_datetime(transactions_df["date"])

# Make sure 'in' and 'out' columns exist
# Rename for clarity
transactions_df = transactions_df.rename(columns={"in": "money_in", "out": "money_out"})

# Add month column
transactions_df["month"] = transactions_df["date"].dt.to_period("M").astype(str)

# Aggregate monthly sums
monthly_summary = (
    transactions_df.groupby("month")
    .agg(
        total_in=pd.NamedAgg(column="money_in", aggfunc="sum"),
        total_out=pd.NamedAgg(column="money_out", aggfunc="sum"),
    )
    .reset_index()
)


# --- Dash App ---
app = dash.Dash(__name__)

app.layout = html.Div(
    [
        html.H1("Monthly Money Summary"),
        dcc.Dropdown(
            id="month-dropdown",
            options=[{"label": m, "value": m} for m in monthly_summary["month"]],
            value=monthly_summary["month"].iloc[-1],
            clearable=False,
        ),
        html.H2("Money In/Out for Selected Month"),
        html.Div(
            [
                dcc.Graph(id="monthly-bar-chart", style={"display": "inline-block"}),
                dcc.Graph(
                    id="monthly-category-chart", style={"display": "inline-block"}
                ),
            ],
            className="row",
        ),
        html.H2("Budget vs Actuals"),
        dcc.Graph(id="monthly-budget-chart"),
        dcc.Dropdown(
            id="num-months-dropdown",
            options=[{"label": m, "value": m} for m in range(1, 64)],
            value=6,
            clearable=False,
        ),
        dcc.Dropdown(
            id="category-dropdown",
            options=[
                {"label": cat, "value": cat}
                for cat in transactions_df["category"].dropna().unique()
            ]
            + [{"label": "All", "value": "All"}],
            value=None,
            clearable=True,
            multi=True,
        ),
        dcc.Graph(id="monthly-line-chart"),
        dcc.Graph(id="cumulative-line-chart"),
        html.H2("Monthly Summary Table"),
        html.Div(id="monthly-summary-table"),
    ]
)


@app.callback(
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

    # Filter for selected month
    selected_month_total_in_out = monthly_summary[
        monthly_summary["month"] == selected_month
    ]

    # --- Total In Out Bar Chart ---

    data = pd.DataFrame(
        {
            "Type": ["Money In", "Money Out"],
            "Amount": [
                selected_month_total_in_out["total_in"].values[0],
                selected_month_total_in_out["total_out"].values[0],
            ],
        }
    )
    figure = px.bar(
        data,
        x="Type",
        y="Amount",
        title=f"Money In/Out for {selected_month}",
        labels={"Type": "Type", "Amount": "Amount"},
        text=data["Amount"].apply(lambda v: f"${v:,.2f}"),
        color="Type",
        color_discrete_map={"Money In": "green", "Money Out": "red"},
    )
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
        title=f"Money In/Out by Category for {selected_month}",
        labels={"value": "Amount", "category": "Category"},
        color_discrete_map={"total_in": "green", "total_out": "red"},
    )

    ### Budget vs Actuals ###
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
        title="Budgeted vs Actual by Category",
        labels={"Value": "Amount ($)", "Category": "Category", "Type": "Type"},
        text=budget_data["Value"].apply(lambda v: f"${v:,.2f}"),
    )

    start_month = str(pd.Period(selected_month, freq="M") - (num_months - 1))

    # line plot for previous 6 months
    if selected_category and "All" not in selected_category:
        if isinstance(selected_category, str):
            selected_category = [selected_category]

        filtered_category_monthly = category_monthly[
            category_monthly["category"].isin(selected_category)
        ]
        prev_months = filtered_category_monthly[
            (filtered_category_monthly["month"] >= start_month)
            & (filtered_category_monthly["month"] <= selected_month)
        ]

        categories = prev_months["category"].unique()

        line_figure = go.Figure()

        color_palette = px.colors.qualitative.Plotly
        color_cycle = itertools.cycle(color_palette)
        category_colors = {cat: next(color_cycle) for cat in categories}

        for cat in categories:
            cat_data = prev_months[prev_months["category"] == cat]
            # add 0 for months with no data
            all_months = pd.period_range(
                start=start_month, end=selected_month, freq="M"
            ).astype(str)
            cat_data = (
                cat_data.set_index("month")
                .reindex(all_months, fill_value=0)
                .reset_index()
                .rename(columns={"index": "month"})
            )
            # Money In: solid line
            line_figure.add_trace(
                go.Scatter(
                    x=cat_data["month"],
                    y=cat_data["total_in"],
                    mode="lines",
                    name=f"{cat} In",
                    line=dict(color=category_colors[cat], dash="dash"),
                )
            )
            # Money Out: dashed line
            line_figure.add_trace(
                go.Scatter(
                    x=cat_data["month"],
                    y=cat_data["total_out"],
                    mode="lines",
                    name=f"{cat} Out",
                    line=dict(color=category_colors[cat], dash="solid"),
                )
            )

        line_figure.update_layout(
            title=f"Money In/Out By Category for Last {num_months} Months up to {selected_month}",
            xaxis_title="Month",
            yaxis_title="Amount",
        )

    else:
        prev_months = monthly_summary[
            (monthly_summary["month"] >= start_month)
            & (monthly_summary["month"] <= selected_month)
        ]
        average_in = prev_months["total_in"].mean()
        average_out = prev_months["total_out"].mean()

        line_figure = px.line(
            prev_months,
            x="month",
            y=["total_in", "total_out"],
            title=f"Money In/Out for Last {num_months} Months up to {selected_month}",
            labels={"value": "Amount", "month": "Month"},
            color_discrete_map={"total_in": "green", "total_out": "red"},
        )

        line_figure = line_figure.add_hline(
            y=average_in,
            annotation_text=f"Average In: {average_in:,.2f}",
            line_dash="dash",
            line_color="green",
        )

        line_figure = line_figure.add_hline(
            y=average_out,
            annotation_text=f"Average Out: {average_out:,.2f}",
            line_dash="dash",
            line_color="red",
        )

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
        title=f"Cumulative Money for Last {num_months} Months up to {selected_month}",
        labels={"value": "Amount", "month": "Month"},
        color_discrete_map={
            "cumulative": "blue",
            "cumulative_rolling_avg": "lightblue",
        },
    )

    transactions = transactions_df[transactions_df["month"] == selected_month]
    # Format columns for display
    transactions_display = transactions.copy()
    transactions_display["date"] = pd.to_datetime(
        transactions_display["date"]
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
        data=transactions_display.to_dict("records"),
        style_table={"overflowX": "auto"},
        style_cell={"textAlign": "left"},
        sort_action="native",
        filter_action="native",
    )
    logger.info("Update complete")

    return (
        figure,
        line_figure,
        table,
        category_figure,
        budget_bar_fig,
        cumulative_line_figure,
    )


if __name__ == "__main__":
    app.run(debug=True)
