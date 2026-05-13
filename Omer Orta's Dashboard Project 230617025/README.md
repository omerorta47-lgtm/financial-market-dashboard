# Financial Market Dashboard

This project is a Streamlit dashboard with three sections:

1. Financial Markets
2. Crypto Fear & Greed Index
3. Pentagon Pizza Index

## Financial Markets Features

- Downloads 1 month of 1-hour data
- Stores data as CSV inside the `data/` folder
- Candlestick price chart
- Bullish vs bearish pie chart
- Volume chart
- Market Watch table
- RSI chart
- MACD chart
- Technical indicator table
- Data table
- CSV download button

## Crypto Fear & Greed Index Features

- Current Crypto Fear & Greed value
- Sentiment classification
- Gauge chart
- Pie chart
- Historical line chart
- Data table
- CSV download button

## Pentagon Pizza Index Features

- Separate sidebar section
- Public Pentagon Pizza Index status
- DOUGHCON-style gauge
- Pizza activity bar chart
- Pizza signal pie chart
- Pizza activity table
- CSV download button

## Technical Indicators Used

- SMA 20
- EMA 20
- RSI 14
- Bollinger Bands
- MACD
- Volatility 20

## Data Sources

- Financial market data: `yfinance`
- Crypto Fear & Greed Index: Alternative.me public API
- Pentagon Pizza Index: PizzINT.watch public page

## Run

Install requirements:

```bash
pip install -r requirements.txt
```

Windows alternative:

```bash
py -m pip install -r requirements.txt
```

Run:

```bash
streamlit run dashboard.py
```

Windows alternative:

```bash
py -m streamlit run dashboard.py
```

## Notes

The dashboard tries to fetch fresh data when it runs. If fetching fails for market data or index pages, saved CSV data may be used when available.

The Fear & Greed Index and Pentagon Pizza Index are sentiment/OSINT-style indicators. They are not investment advice and do not prove future events.
