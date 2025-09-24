import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go

# Read the transactions CSV
df = pd.read_csv('src/budget/data/transactions.csv')
df['date'] = pd.to_datetime(df['date'])

# Make sure 'in' and 'out' columns exist
# Rename for clarity
df = df.rename(columns={'in': 'money_in', 'out': 'money_out'})

# Add month column
df['month'] = df['date'].dt.to_period('M').astype(str)

# Aggregate monthly sums
monthly_summary = df.groupby('month').agg(
    total_in=pd.NamedAgg(column='money_in', aggfunc='sum'),
    total_out=pd.NamedAgg(column='money_out', aggfunc='sum')
).reset_index()

# Aggregate by category and month for line plot
category_monthly = df.groupby(['month', 'category']).agg(
    total_in=pd.NamedAgg(column='money_in', aggfunc='sum'),
    total_out=pd.NamedAgg(column='money_out', aggfunc='sum')
).reset_index()

# --- Dash App ---
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Monthly Money Summary"),
    
    dcc.Dropdown(
        id='month-dropdown',
        options=[{'label': m, 'value': m} for m in monthly_summary['month']],
        value=monthly_summary['month'].iloc[-1],
        clearable=False
    ),
    html.Div([
        dcc.Graph(id='monthly-bar-chart', style={'display': 'inline-block'}),
        dcc.Graph(id='monthly-category-chart', style={'display': 'inline-block'})
    ], className='row'),

    dcc.Dropdown(
        id='num-months-dropdown',
        options=[{'label': m, 'value': m} for m in range(1,64)],
        value=6,
        clearable=False
    ),
    dcc.Dropdown(
        id = "category-dropdown",
        options = [{'label': cat, 'value': cat} for cat in df['category'].dropna().unique()] + [{'label': 'All', 'value': 'All'}],
        value = None,
        clearable = True,
        multi=True,
    ),

    dcc.Graph(id='monthly-line-chart'),
    
    html.H2("Monthly Summary Table"),
    html.Div(id='monthly-summary-table')
])


@app.callback(
    Output('monthly-bar-chart', 'figure'),
    Output('monthly-line-chart', 'figure'),
    Output('monthly-summary-table', 'children'),
    Output('monthly-category-chart', 'figure'),
    Input('month-dropdown', 'value'),
    Input('num-months-dropdown', 'value'),
    Input('category-dropdown', 'value')
)
def update_chart(selected_month, num_months, selected_category):
    # Filter for selected month
    filtered_overall = monthly_summary[monthly_summary['month'] == selected_month]
    filtered_with_category = category_monthly[category_monthly['month'] == selected_month]
    # Bar chart

    data = pd.DataFrame({
    "Type": ["Money In", "Money Out"],
    "Amount": [filtered_overall['total_in'].values[0], 
               filtered_overall['total_out'].values[0]]
    })
    figure = px.bar(
        data,
        x="Type",
        y="Amount",
        title=f"Money In/Out for {selected_month}",
        labels={"Type": "Type", "Amount": "Amount"},
        text=data["Amount"].apply(lambda v: f"${v:,.2f}"),
        color="Type",
        color_discrete_map={"Money In": "green", "Money Out": "red"}
    )

    data = [[{'x': category,
             'y': -filtered_with_category['total_in'],
             'type': 'bar',
             'name': category,
             'marker': {'color': 'green'}},
            {'x': category,
             'y': filtered_with_category['total_out'],
             'type': 'bar',
             'name': category,
             'marker': {'color': 'red'}}] for category in filtered_with_category['category'].unique()]
    
    # flatten the list of lists
    data = [item for sublist in data for item in sublist]


    # Category bar chart
    category_figure = px.bar(
        filtered_with_category,
        x='category',
        y=['total_in', 'total_out'],
        barmode='group',
        title=f'Money In/Out by Category for {selected_month}',
        labels={'value': 'Amount', 'category': 'Category'},
        color_discrete_map={'total_in': 'green', 'total_out': 'red'}
    )

    start_month = str(pd.Period(selected_month, freq='M') - (num_months - 1))

    # line plot for previous 6 months
    if selected_category and 'All' not in selected_category:
        if isinstance(selected_category, str):
            selected_category = [selected_category]

        filtered_category_monthly = category_monthly[category_monthly['category'].isin(selected_category)]
        prev_months = filtered_category_monthly[(filtered_category_monthly['month'] >= start_month) & (filtered_category_monthly['month'] <= selected_month)]

        categories = prev_months['category'].unique()

        line_figure = go.Figure()

        import itertools
        color_palette = px.colors.qualitative.Plotly
        color_cycle = itertools.cycle(color_palette)
        category_colors = {cat: next(color_cycle) for cat in categories}
        
        for cat in categories:
            cat_data = prev_months[prev_months['category'] == cat]
            # add 0 for months with no data
            all_months = pd.period_range(start=start_month, end=selected_month, freq='M').astype(str)
            cat_data = cat_data.set_index('month').reindex(all_months, fill_value=0).reset_index().rename(columns={'index': 'month'})
            # Money In: solid line
            line_figure.add_trace(go.Scatter(
                x=cat_data['month'],
                y=cat_data['total_in'],
                mode='lines',
                name=f"{cat} In",
                line=dict(color=category_colors[cat], dash='dash')
            ))
            # Money Out: dashed line
            line_figure.add_trace(go.Scatter(
                x=cat_data['month'],
                y=cat_data['total_out'],
                mode='lines',
                name=f"{cat} Out",
                line=dict(color=category_colors[cat], dash='solid')
            ))

        line_figure.update_layout(
            title=f'Money In/Out By Category for Last {num_months} Months up to {selected_month}',
            xaxis_title='Month',
            yaxis_title='Amount'
        )

    else:
        prev_months = monthly_summary[monthly_summary['month'] <= selected_month].tail(num_months)
        prev_months = monthly_summary[(monthly_summary['month'] >= start_month) & (monthly_summary['month'] <= selected_month)]

        line_figure = px.line(
            prev_months,
            x='month',
            y=['total_in', 'total_out'],
            title=f'Money In/Out for Last {num_months} Months up to {selected_month}',
            labels={'value': 'Amount', 'month': 'Month'},
            color_discrete_map={'total_in': 'green', 'total_out': 'red'}
        )

    transactions = df[df['month'] == selected_month]
    # Format columns for display
    transactions_display = transactions.copy()
    transactions_display['date'] = transactions_display['date'].dt.strftime('%Y-%m-%d')


    # Table

    table = dash_table.DataTable(
    columns=[
        {"name": "Date", "id": "date"},
        {"name": "Description", "id": "description"},
        {"name": "Category", "id": "category"},
        {"name": "Money In", "id": "money_in"},
        {"name": "Money Out", "id": "money_out"},
    ],
        data=transactions_display.to_dict('records'),
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'},
        sort_action='native',
    )

    return figure, line_figure, table, category_figure

if __name__ == '__main__':
    app.run(debug=True)
