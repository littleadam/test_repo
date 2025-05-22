"""
Main entry point for the Iron Condor Options Trading Application.
Integrates the trading strategy with the Streamlit dashboard in a Google Colab environment.
"""

import os
import sys
import time
import logging
import threading
import datetime
import json
import traceback
from typing import Dict, Any

import streamlit as st
import pandas as pd
import numpy as np

# Import custom modules
from mstock_api_client import MStockAPI
from iron_condor_strategy import IronCondorStrategy
from streamlit_dashboard import StreamlitDashboard, run_streamlit_in_thread
from date_utils import get_expiry_date_n_weeks_ahead, is_trading_day, get_next_trading_day, is_trading_time
from models import Order, OrderType, OrderSide, OrderStatus, ProductType, OptionType, Position, OptionContract, OptionChain

# Default configuration
DEFAULT_CONFIG = {
    "API_CONFIG": {
        "api_key": "",  # To be filled by user
        "username": "",  # To be filled by user
        "password": "",  # To be filled by user
        "api_url": "https://api.mstock.trade",
        "ws_url": "https://ws.mstock.trade",
        "version": "1"
    },
    "INVESTMENT_CONFIG": {
        "base_investment": 200000,  # Base investment amount
        "lot_size": 75,  # Lot size for Nifty options
        "lots_per_investment": 1,  # Number of lots per 150,000 investment
        "investment_per_lot": 150000,  # Investment amount per lot
    },
    "STRATEGY_CONFIG": {
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
    },
    "TRADING_HOURS": {
        "start_time": "09:15:00",
        "end_time": "15:30:00",
        "check_interval": 300,  # Check positions every 5 minutes (in seconds)
    },
    "HOLIDAYS": [
        # Format: "YYYY-MM-DD"
        # To be filled by user
    ],
    "LOGGING_CONFIG": {
        "log_level": "INFO",
        "log_file": "trading_app.log",
        "error_log_file": "error.log",
    },
    "RECONNECTION_CONFIG": {
        "check_interval": 600,  # Check connection every 10 minutes (in seconds)
        "max_retries": 5,  # Maximum number of reconnection attempts
        "retry_delay": 60,  # Delay between reconnection attempts (in seconds)
    },
    "DASHBOARD_CONFIG": {
        "refresh_interval": 10,  # Dashboard refresh interval (in seconds)
        "chart_height": 400,  # Height of charts in pixels
        "chart_width": 800,  # Width of charts in pixels
        "log_lines": 50,  # Number of log lines to display
        "error_log_lines": 20,  # Number of error log lines to display
    }
}

class IronCondorApp:
    """
    Main application class for the Iron Condor Options Trading Application.
    """
    
    def __init__(self):
        """
        Initialize the application.
        """
        self.config = self._load_config()
        self._setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing Iron Condor Options Trading Application")
        self.api = None
        self.strategy = None
        self.dashboard = None
        self.is_running = False
        self.reconnect_thread = None
        self.reconnect_attempts = 0
        self.last_reconnect_time = None
        
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or use default.
        
        Returns:
            Configuration dictionary
        """
        config_file = "config.json"
        
        if os.path.exists(config_file):
            try:
                with open(config_file, "r") as f:
                    config = json.load(f)
                print(f"Configuration loaded from {config_file}")
                return config
            except Exception as e:
                print(f"Error loading configuration from {config_file}: {str(e)}")
                print("Using default configuration")
                return DEFAULT_CONFIG
        else:
            print(f"Configuration file {config_file} not found. Using default configuration.")
            return DEFAULT_CONFIG
            
    def _setup_logging(self):
        """
        Set up logging configuration.
        """
        log_level = getattr(logging, self.config["LOGGING_CONFIG"]["log_level"])
        log_file = self.config["LOGGING_CONFIG"]["log_file"]
        error_log_file = self.config["LOGGING_CONFIG"]["error_log_file"]
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(os.path.join("logs", log_file)),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Configure error logger
        error_logger = logging.getLogger("error")
        error_logger.setLevel(logging.ERROR)
        error_handler = logging.FileHandler(os.path.join("logs", error_log_file))
        error_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        error_logger.addHandler(error_handler)
        
        print(f"Logging configured. Log files: logs/{log_file}, logs/{error_log_file}")
        
    def initialize(self) -> bool:
        """
        Initialize the application components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing application components")
        try:
            # Initialize API client
            self.logger.info("Initializing API client")
            self.api = MStockAPI(
                api_key=self.config["API_CONFIG"]["api_key"],
                username=self.config["API_CONFIG"]["username"],
                password=self.config["API_CONFIG"]["password"],
                api_url=self.config["API_CONFIG"]["api_url"],
                ws_url=self.config["API_CONFIG"]["ws_url"],
                version=self.config["API_CONFIG"]["version"]
            )
            
            # Initialize strategy
            self.logger.info("Initializing trading strategy")
            self.strategy = IronCondorStrategy(self.api, self.config)
            
            # Add additional attributes needed by the dashboard
            self.strategy.is_running = False
            self.strategy.last_reconnect_time = datetime.datetime.now()
            self.strategy.reconnect_attempts = 0
            self.strategy.start = self.start
            self.strategy.stop = self.stop
            self.strategy.close_all_positions = self.close_all_positions
            self.strategy.reconnect = self.reconnect
            
            # Initialize dashboard
            self.logger.info("Initializing Streamlit dashboard")
            self.dashboard = StreamlitDashboard(self.strategy, self.config)
            
            self.logger.info("Application initialized successfully")
            return True
        except Exception as e:
            self.logger.error(f"Initialization error: {str(e)}", exc_info=True)
            return False
            
    def start(self):
        """
        Start the trading strategy.
        """
        if self.is_running:
            self.logger.info("Trading strategy is already running")
            return
            
        self.logger.info("Starting trading strategy")
        self.is_running = True
        self.strategy.is_running = True
        
        # Start strategy in a separate thread
        self.logger.debug("Starting strategy thread")
        threading.Thread(target=self._run_strategy, daemon=True).start()
        
        # Start reconnection thread
        self.logger.debug("Starting reconnection monitor thread")
        self.reconnect_thread = threading.Thread(target=self._reconnection_monitor, daemon=True)
        self.reconnect_thread.start()
        
        self.logger.info("Trading strategy started successfully")
        
    def stop(self):
        """
        Stop the trading strategy.
        """
        if not self.is_running:
            self.logger.info("Trading strategy is not running")
            return
            
        self.logger.info("Stopping trading strategy")
        self.is_running = False
        self.strategy.is_running = False
        
        self.logger.info("Trading strategy stopped successfully")
        
    def close_all_positions(self):
        """
        Close all open positions.
        """
        if not self.api or not self.strategy:
            self.logger.error("API or strategy not initialized")
            return False
            
        self.logger.info("Closing all open positions")
        try:
            # Get all positions
            positions = self.strategy.active_positions
            
            if not positions:
                self.logger.info("No positions to close")
                return True
                
            # Close each position
            for symbol, position in positions.items():
                self.logger.info(f"Closing position for {symbol}")
                close_params = {
                    "trading_symbol": symbol,
                    "exchange": position.exchange,
                    "transaction_type": "BUY" if position.side == OrderSide.SELL else "SELL",
                    "order_type": "MARKET",
                    "quantity": position.quantity,
                    "product": position.product.value,
                    "price": 0  # Market order
                }
                
                result = self.api.place_order(close_params)
                
                if result:
                    self.logger.info(f"Closed position for {symbol} successfully")
                else:
                    self.logger.error(f"Failed to close position for {symbol}")
                    return False
                    
            self.logger.info("All positions closed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error closing positions: {str(e)}", exc_info=True)
            return False
            
    def reconnect(self):
        """
        Reconnect to the API.
        """
        self.logger.info("Attempting to reconnect to API")
        try:
            # Stop the strategy
            was_running = self.is_running
            self.stop()
            
            # Reinitialize API client
            self.logger.debug("Reinitializing API client")
            self.api = MStockAPI(
                api_key=self.config["API_CONFIG"]["api_key"],
                username=self.config["API_CONFIG"]["username"],
                password=self.config["API_CONFIG"]["password"],
                api_url=self.config["API_CONFIG"]["api_url"],
                ws_url=self.config["API_CONFIG"]["ws_url"],
                version=self.config["API_CONFIG"]["version"]
            )
            
            # Login
            self.logger.debug("Logging in to API")
            if not self.api.login():
                self.logger.error("Reconnection failed: Login failed")
                return False
                
            # Update strategy with new API client
            self.strategy.api = self.api
            
            # Restart if it was running
            if was_running:
                self.logger.debug("Restarting strategy")
                self.start()
                
            self.last_reconnect_time = datetime.datetime.now()
            self.strategy.last_reconnect_time = self.last_reconnect_time
            self.reconnect_attempts = 0
            self.strategy.reconnect_attempts = 0
            
            self.logger.info("Reconnection successful")
            return True
        except Exception as e:
            self.logger.error(f"Reconnection error: {str(e)}", exc_info=True)
            return False
            
    def _run_strategy(self):
        """
        Run the trading strategy in a loop.
        """
        self.logger.info("Strategy thread started")
        try:
            # Initialize strategy
            self.logger.debug("Initializing strategy")
            if not self.strategy.initialize():
                self.logger.error("Failed to initialize strategy")
                self.is_running = False
                self.strategy.is_running = False
                return
                
            # Main strategy loop
            self.logger.info("Entering main strategy loop")
            while self.is_running:
                try:
                    # Check if it's a trading day and within trading hours
                    now = datetime.datetime.now()
                    today = now.date()
                    current_time = now.time()
                    
                    if not is_trading_day(today, self.config["HOLIDAYS"]):
                        self.logger.info(f"Not a trading day: {today}")
                        time.sleep(self.config["TRADING_HOURS"]["check_interval"])
                        continue
                        
                    start_time = datetime.datetime.strptime(self.config["TRADING_HOURS"]["start_time"], "%H:%M:%S").time()
                    end_time = datetime.datetime.strptime(self.config["TRADING_HOURS"]["end_time"], "%H:%M:%S").time()
                    
                    if not is_trading_time(current_time, start_time, end_time):
                        self.logger.info(f"Outside trading hours: {current_time}")
                        time.sleep(self.config["TRADING_HOURS"]["check_interval"])
                        continue
                        
                    # Run strategy logic
                    self.logger.debug("Executing strategy logic")
                    investment_amount = self.strategy.calculate_investment_amount()
                    self.logger.debug(f"Investment amount: {investment_amount}")
                    
                    spot_price = self.strategy._get_spot_price()
                    if spot_price is None:
                        self.logger.error("Failed to get spot price")
                        time.sleep(60)  # Short sleep before retry
                        continue
                    self.logger.debug(f"Current spot price: {spot_price}")
                    
                    # Update positions
                    self.logger.debug("Updating positions")
                    self.strategy._update_positions()
                    
                    # Check if we need to place initial positions
                    if not self.strategy.active_positions:
                        self.logger.info("No active positions, placing short strangle")
                        self.strategy.place_short_strangle(investment_amount, spot_price)
                        
                    # Check for stop loss and martingale conditions
                    self.logger.debug("Checking stop loss and martingale conditions")
                    for symbol, position in self.strategy.active_positions.items():
                        if position.side == OrderSide.SELL:  # Only check sell positions
                            self.logger.debug(f"Checking position {symbol}")
                            current_price = self.strategy._get_current_price(position.symbol)
                            if current_price is None:
                                self.logger.warning(f"Failed to get current price for {symbol}")
                                continue
                                
                            # Get option chain for the position's expiry
                            option_chain = self.strategy.get_option_chain_for_expiry(position.expiry_date.date())
                            if option_chain is None:
                                self.logger.warning(f"Failed to get option chain for {position.expiry_date.date()}")
                                continue
                                
                            # Check stop loss
                            self.logger.debug(f"Checking stop loss for {symbol}")
                            self.strategy.handle_stop_loss(position, current_price)
                            
                            # Check martingale
                            self.logger.debug(f"Checking martingale for {symbol}")
                            self.strategy.handle_martingale(position, current_price, option_chain)
                            
                    # Check if we need to close positions at expiry
                    self.logger.debug("Checking positions for expiry")
                    self.strategy.close_positions_at_expiry()
                    
                    # Check if we need to roll hedge positions
                    self.logger.debug("Checking hedge positions for rolling")
                    self.strategy.roll_hedge_positions()
                    
                    # Sleep before next check
                    self.logger.debug(f"Sleeping for {self.config['TRADING_HOURS']['check_interval']} seconds")
                    time.sleep(self.config["TRADING_HOURS"]["check_interval"])
                    
                except Exception as e:
                    self.logger.error(f"Error in strategy loop: {str(e)}", exc_info=True)
                    self.logger.error(traceback.format_exc())
                    time.sleep(60)  # Short sleep before retry
                    
        except Exception as e:
            self.logger.error(f"Fatal error in strategy thread: {str(e)}", exc_info=True)
            self.logger.error(traceback.format_exc())
            self.is_running = False
            self.strategy.is_running = False
            
    def _reconnection_monitor(self):
        """
        Monitor connection and reconnect if necessary.
        """
        self.logger.info("Reconnection monitor thread started")
        while self.is_running:
            try:
                self.logger.debug(f"Sleeping for {self.config['RECONNECTION_CONFIG']['check_interval']} seconds")
                time.sleep(self.config["RECONNECTION_CONFIG"]["check_interval"])
                
                # Check if we need to reconnect
                if not self.api or not self.strategy:
                    self.logger.warning("API or strategy not initialized, skipping connection check")
                    continue
                    
                # Try a simple API call to check connection
                self.logger.debug("Checking API connection")
                fund_summary = self.api.get_fund_summary()
                
                if fund_summary is None:
                    self.logger.warning("Connection check failed, attempting to reconnect")
                    
                    # Increment reconnect attempts
                    self.reconnect_attempts += 1
                    self.strategy.reconnect_attempts = self.reconnect_attempts
                    self.logger.info(f"Reconnect attempt {self.reconnect_attempts} of {self.config['RECONNECTION_CONFIG']['max_retries']}")
                    
                    # Check if we've exceeded max retries
                    if self.reconnect_attempts > self.config["RECONNECTION_CONFIG"]["max_retries"]:
                        self.logger.error("Max reconnection attempts exceeded")
                        self.stop()
                        break
                        
                    # Attempt to reconnect
                    if not self.reconnect():
                        self.logger.warning(f"Reconnection failed, waiting {self.config['RECONNECTION_CONFIG']['retry_delay']} seconds before retry")
                        time.sleep(self.config["RECONNECTION_CONFIG"]["retry_delay"])
                else:
                    self.logger.debug("Connection check successful")
                        
            except Exception as e:
                self.logger.error(f"Error in reconnection monitor: {str(e)}", exc_info=True)
                time.sleep(60)  # Short sleep before retry
                
    def run(self):
        """
        Run the application.
        """
        self.logger.info("Starting application")
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return
            
        # Set up Streamlit for Colab environment
        self.logger.info("Setting up Streamlit for Colab environment")
        os.environ['STREAMLIT_SERVER_PORT'] = "8501"
        os.environ['STREAMLIT_SERVER_HEADLESS'] = "true"
        os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = "none"
        
        # Run the Streamlit dashboard in a separate thread to avoid the
        # "mainthread missing scriptruncontext" warning
        self.logger.info("Starting Streamlit dashboard in a separate thread")
        dashboard_thread = threading.Thread(
            target=run_streamlit_in_thread,
            args=(self.dashboard,),
            daemon=True
        )
        dashboard_thread.start()
        
        # Keep the main thread alive
        self.logger.info("Main thread waiting for dashboard thread")
        try:
            while dashboard_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received, stopping application")
            self.stop()
        
        self.logger.info("Application stopped")

def main():
    """
    Main entry point.
    """
    print("Starting Iron Condor Options Trading Application")
    app = IronCondorApp()
    app.run()

if __name__ == "__main__":
    main()
