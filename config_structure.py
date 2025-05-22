"""
Configuration structure for the Iron Condor Options Trading Application.
All parameters are configurable to allow easy adjustment of the trading strategy.
"""

# API Configuration
API_CONFIG = {
    "api_key": "",  # To be filled by user
    "username": "",  # To be filled by user
    "password": "",  # To be filled by user
    "api_url": "https://api.mstock.trade",
    "ws_url": "https://ws.mstock.trade",
    "version": "1"
}

# Investment Configuration
INVESTMENT_CONFIG = {
    "base_investment": 200000,  # Base investment amount
    "lot_size": 75,  # Lot size for Nifty options
    "lots_per_investment": 1,  # Number of lots per 150,000 investment
    "investment_per_lot": 150000,  # Investment amount per lot
}

# Strategy Configuration
STRATEGY_CONFIG = {
    "target_monthly_return": 0.04,  # 4% target monthly return
    "leg_premium_target": 0.025,  # Each leg premium around 2.5% of investment
    "strangle_distance": 1000,  # Points away from spot price for short strangle
    "sell_expiry_weeks": 5,  # Sell orders expire after 5 weeks
    "close_after_weeks": 4,  # Close sell orders after 4 weeks
    "hedge_expiry_weeks": 1,  # Hedge buy orders expire after 1 week (current week)
    "stop_loss_trigger": 0.25,  # Trigger stop loss when sell order drops by 25%
    "stop_loss_percentage": 0.90,  # 90% stop loss
    "martingale_trigger": 2.0,  # Trigger martingale when sell leg doubles in price
    "martingale_quantity_multiplier": 2.0,  # Double quantity for martingale sell orders
    "martingale_premium_divisor": 2.0,  # Half premium for martingale sell orders
}

# Trading Hours Configuration
TRADING_HOURS = {
    "start_time": "09:15:00",
    "end_time": "15:30:00",
    "check_interval": 300,  # Check positions every 5 minutes (in seconds)
}

# Holiday Configuration
HOLIDAYS = [
    # Format: "YYYY-MM-DD"
    # To be filled by user
]

# Logging Configuration
LOGGING_CONFIG = {
    "log_level": "INFO",
    "log_file": "trading_app.log",
    "error_log_file": "error.log",
}

# Colab Reconnection Configuration
RECONNECTION_CONFIG = {
    "check_interval": 600,  # Check connection every 10 minutes (in seconds)
    "max_retries": 5,  # Maximum number of reconnection attempts
    "retry_delay": 60,  # Delay between reconnection attempts (in seconds)
}

# Streamlit Dashboard Configuration
DASHBOARD_CONFIG = {
    "refresh_interval": 10,  # Dashboard refresh interval (in seconds)
    "chart_height": 400,  # Height of charts in pixels
    "chart_width": 800,  # Width of charts in pixels
    "log_lines": 50,  # Number of log lines to display
    "error_log_lines": 20,  # Number of error log lines to display
}
