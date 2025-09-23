import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

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
    
    dcc.Graph(id='monthly-bar-chart'),

    dcc.Dropdown(
        id='num-months-dropdown',
        options=[{'label': m, 'value': m} for m in range(1,64)],
        value=6,
        clearable=False
    ),

    dcc.Graph(id='monthly-line-chart'),
    
    html.H2("Monthly Summary Table"),
    html.Div(id='monthly-summary-table')
])


@app.callback(
    Output('monthly-bar-chart', 'figure'),
    Output('monthly-line-chart', 'figure'),
    Output('monthly-summary-table', 'children'),
    Input('month-dropdown', 'value'),
    Input('num-months-dropdown', 'value')
)
def update_chart(selected_month, num_months):
    # Filter for selected month
    filtered = monthly_summary[monthly_summary['month'] == selected_month]
    
    # Bar chart
    figure = {
        'data': [
            {'x': ['Money In', 'Money Out'],
             'y': [filtered['total_in'].values[0], filtered['total_out'].values[0]],
             'type': 'bar',
             'marker': {'color': ['green', 'red']}}
        ],
        'layout': {'title': f'Money In/Out for {selected_month}'}
    }

    # line plot for previous 6 months
    prev_months = monthly_summary[monthly_summary['month'] <= selected_month].tail(num_months)

    line_figure = {
        'data': [
            {'x': prev_months['month'],
             'y': prev_months['total_in'],
             'type': 'line',
             'name': 'Money In',
             'marker': {'color': 'green'}},
            {'x': prev_months['month'],
             'y': prev_months['total_out'],
             'type': 'line',
             'name': 'Money Out',
             'marker': {'color': 'red'}}
        ],
        'layout': {'title': f'Money In/Out for Last 6 Months up to {selected_month}'}
    }

    # Table
    table = html.Table([
        html.Thead(html.Tr([html.Th("Month"), html.Th("Money In"), html.Th("Money Out")])),
        html.Tbody([
            html.Tr([
                html.Td(filtered['month'].values[0]),
                html.Td(f"${filtered['total_in'].values[0]:,.2f}"),
                html.Td(f"${filtered['total_out'].values[0]:,.2f}")
            ])
        ])
    ])

    return figure, line_figure, table

if __name__ == '__main__':
    app.run(debug=True)
