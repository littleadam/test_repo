"""
Streamlit dashboard for the Iron Condor Options Trading Application.
Provides real-time monitoring, configuration, and control.
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import time
import datetime
import json
import os
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple

# Configure logger
logger = logging.getLogger(__name__)

class StreamlitDashboard:
    """
    Streamlit dashboard for monitoring and controlling the Iron Condor strategy.
    """
    
    def __init__(self, strategy, config):
        """
        Initialize the dashboard.
        
        Args:
            strategy: Strategy instance
            config: Configuration dictionary
        """
        self.strategy = strategy
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.info("Streamlit dashboard initialized")
        
    def run(self):
        """
        Run the Streamlit dashboard.
        """
        self.logger.info("Starting Streamlit dashboard")
        
        # Set up Streamlit for Colab environment
        # This helps address the "mainthread missing scriptruncontext" warning
        os.environ['STREAMLIT_SERVER_PORT'] = "8501"
        os.environ['STREAMLIT_SERVER_HEADLESS'] = "true"
        os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = "none"
        
        # Configure Streamlit page
        st.set_page_config(
            page_title="Iron Condor Options Trading Dashboard",
            page_icon="📈",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        self.logger.info("Streamlit page configuration set")
        
        # Set up sidebar
        self._setup_sidebar()
        
        # Main page layout
        st.title("Iron Condor Options Trading Dashboard")
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["Positions", "Strategy Configuration", "P&L Analysis", "Logs"])
        
        with tab1:
            self.logger.debug("Rendering positions tab")
            self._render_positions_tab()
            
        with tab2:
            self.logger.debug("Rendering strategy configuration tab")
            self._render_strategy_config_tab()
            
        with tab3:
            self.logger.debug("Rendering P&L tab")
            self._render_pnl_tab()
            
        with tab4:
            self.logger.debug("Rendering logs tab")
            self._render_logs_tab()
            
        # Auto-refresh
        self.logger.debug(f"Sleeping for {self.config['DASHBOARD_CONFIG']['refresh_interval']} seconds before refresh")
        time.sleep(self.config["DASHBOARD_CONFIG"]["refresh_interval"])
        
        # Use st.rerun() instead of st.experimental_rerun()
        self.logger.debug("Triggering dashboard rerun")
        st.rerun()
        
    def _setup_sidebar(self):
        """
        Set up the sidebar with controls and status.
        """
        self.logger.debug("Setting up sidebar")
        st.sidebar.title("Trading Controls")
        
        # Status indicator
        status = "🟢 Running" if self.strategy.is_running else "🔴 Stopped"
        st.sidebar.markdown(f"### Status: {status}")
        self.logger.debug(f"Strategy status: {status}")
        
        # Account information
        st.sidebar.markdown("### Account Information")
        try:
            investment_amount = self.strategy.calculate_investment_amount()
            st.sidebar.metric("Total Investment", f"₹{investment_amount:,.2f}")
            self.logger.debug(f"Total investment: ₹{investment_amount:,.2f}")
        except Exception as e:
            st.sidebar.error("Failed to fetch investment amount")
            self.logger.error(f"Error fetching investment amount: {str(e)}", exc_info=True)
        
        # Current P&L
        try:
            total_pnl = self._calculate_total_pnl()
            pnl_color = "green" if total_pnl >= 0 else "red"
            st.sidebar.markdown(f"### Current P&L: <span style='color:{pnl_color}'>₹{total_pnl:,.2f}</span>", unsafe_allow_html=True)
            self.logger.debug(f"Current P&L: ₹{total_pnl:,.2f}")
        except Exception as e:
            st.sidebar.error("Failed to calculate P&L")
            self.logger.error(f"Error calculating P&L: {str(e)}", exc_info=True)
        
        # Control buttons
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            if st.button("Start Trading", disabled=self.strategy.is_running):
                self.logger.info("Start Trading button clicked")
                try:
                    self.strategy.start()
                    st.success("Trading started")
                    self.logger.info("Trading started successfully")
                except Exception as e:
                    st.error(f"Failed to start trading: {str(e)}")
                    self.logger.error(f"Error starting trading: {str(e)}", exc_info=True)
                
        with col2:
            if st.button("Stop Trading", disabled=not self.strategy.is_running):
                self.logger.info("Stop Trading button clicked")
                try:
                    self.strategy.stop()
                    st.success("Trading stopped")
                    self.logger.info("Trading stopped successfully")
                except Exception as e:
                    st.error(f"Failed to stop trading: {str(e)}")
                    self.logger.error(f"Error stopping trading: {str(e)}", exc_info=True)
                
        # Emergency button
        if st.sidebar.button("🚨 CLOSE ALL POSITIONS", type="primary"):
            self.logger.warning("Emergency close all positions button clicked")
            if st.sidebar.checkbox("Confirm closing all positions"):
                self.logger.info("Close all positions confirmed")
                try:
                    self.strategy.close_all_positions()
                    st.sidebar.success("All positions closed")
                    self.logger.info("All positions closed successfully")
                except Exception as e:
                    st.sidebar.error(f"Failed to close positions: {str(e)}")
                    self.logger.error(f"Error closing positions: {str(e)}", exc_info=True)
                
        # Reconnection status
        st.sidebar.markdown("### Colab Connection")
        last_reconnect = self.strategy.last_reconnect_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(self.strategy, "last_reconnect_time") else "Never"
        st.sidebar.text(f"Last reconnect: {last_reconnect}")
        reconnect_attempts = getattr(self.strategy, "reconnect_attempts", 0)
        st.sidebar.text(f"Reconnect attempts: {reconnect_attempts}")
        self.logger.debug(f"Last reconnect: {last_reconnect}, Attempts: {reconnect_attempts}")
        
        # Manual reconnect button
        if st.sidebar.button("Force Reconnect"):
            self.logger.info("Force reconnect button clicked")
            try:
                self.strategy.reconnect()
                st.sidebar.success("Reconnection initiated")
                self.logger.info("Reconnection initiated successfully")
            except Exception as e:
                st.sidebar.error(f"Failed to reconnect: {str(e)}")
                self.logger.error(f"Error reconnecting: {str(e)}", exc_info=True)
            
    def _render_positions_tab(self):
        """
        Render the positions tab.
        """
        st.header("Current Positions")
        
        # Get positions data
        try:
            positions = self.strategy.active_positions
            self.logger.debug(f"Fetched {len(positions)} active positions")
            
            if not positions:
                st.info("No active positions")
                return
                
            # Convert positions to DataFrame for display
            positions_data = []
            for symbol, position in positions.items():
                positions_data.append({
                    "Symbol": symbol,
                    "Type": position.option_type.value if position.option_type else "STOCK",
                    "Strike": position.strike_price if position.strike_price else "-",
                    "Expiry": position.expiry_date.strftime("%Y-%m-%d") if position.expiry_date else "-",
                    "Side": position.side.value,
                    "Quantity": position.quantity,
                    "Avg Price": f"₹{position.average_price:.2f}",
                    "Current Price": f"₹{self._get_current_price(symbol):.2f}",
                    "P&L": f"₹{position.pnl:.2f}",
                    "Role": "Hedge" if position.is_hedge else "Martingale" if position.is_martingale else "Primary"
                })
                
            df = pd.DataFrame(positions_data)
            
            # Display positions table
            st.dataframe(df, use_container_width=True)
            self.logger.debug("Positions table rendered")
            
            # Position visualization
            st.subheader("Position Visualization")
            
            # Create payoff diagram
            try:
                fig = self._create_payoff_diagram()
                st.plotly_chart(fig, use_container_width=True)
                self.logger.debug("Payoff diagram rendered")
            except Exception as e:
                st.error(f"Failed to create payoff diagram: {str(e)}")
                self.logger.error(f"Error creating payoff diagram: {str(e)}", exc_info=True)
            
            # Position actions
            st.subheader("Position Actions")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("Roll Hedges"):
                    self.logger.info("Roll hedges button clicked")
                    try:
                        success = self.strategy.roll_hedge_positions()
                        if success:
                            st.success("Hedges rolled successfully")
                            self.logger.info("Hedges rolled successfully")
                        else:
                            st.error("Failed to roll hedges")
                            self.logger.warning("Failed to roll hedges")
                    except Exception as e:
                        st.error(f"Error rolling hedges: {str(e)}")
                        self.logger.error(f"Error rolling hedges: {str(e)}", exc_info=True)
                    
            with col2:
                if st.button("Close Expired Positions"):
                    self.logger.info("Close expired positions button clicked")
                    try:
                        success = self.strategy.close_positions_at_expiry()
                        if success:
                            st.success("Expired positions closed")
                            self.logger.info("Expired positions closed successfully")
                        else:
                            st.info("No expired positions to close")
                            self.logger.info("No expired positions to close")
                    except Exception as e:
                        st.error(f"Error closing expired positions: {str(e)}")
                        self.logger.error(f"Error closing expired positions: {str(e)}", exc_info=True)
                    
            with col3:
                if st.button("Refresh Positions"):
                    self.logger.info("Refresh positions button clicked")
                    try:
                        self.strategy._update_positions()
                        st.success("Positions refreshed")
                        self.logger.info("Positions refreshed successfully")
                    except Exception as e:
                        st.error(f"Error refreshing positions: {str(e)}")
                        self.logger.error(f"Error refreshing positions: {str(e)}", exc_info=True)
        except Exception as e:
            st.error(f"Error rendering positions tab: {str(e)}")
            self.logger.error(f"Error rendering positions tab: {str(e)}", exc_info=True)
                
    def _render_strategy_config_tab(self):
        """
        Render the strategy configuration tab.
        """
        st.header("Strategy Configuration")
        self.logger.debug("Rendering strategy configuration tab")
        
        # Create form for configuration
        with st.form("strategy_config_form"):
            # Investment configuration
            st.subheader("Investment Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                base_investment = st.number_input(
                    "Base Investment (₹)",
                    min_value=100000.0,
                    max_value=10000000.0,
                    value=float(self.config["INVESTMENT_CONFIG"]["base_investment"]),
                    step=10000.0
                )
                
                lot_size = st.number_input(
                    "Lot Size",
                    min_value=1,
                    max_value=1000,
                    value=self.config["INVESTMENT_CONFIG"]["lot_size"],
                    step=1
                )
                
            with col2:
                lots_per_investment = st.number_input(
                    "Lots per Investment",
                    min_value=1,
                    max_value=10,
                    value=self.config["INVESTMENT_CONFIG"]["lots_per_investment"],
                    step=1
                )
                
                investment_per_lot = st.number_input(
                    "Investment per Lot (₹)",
                    min_value=10000.0,
                    max_value=1000000.0,
                    value=float(self.config["INVESTMENT_CONFIG"]["investment_per_lot"]),
                    step=10000.0
                )
                
            # Strategy configuration
            st.subheader("Strategy Configuration")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                target_monthly_return = st.number_input(
                    "Target Monthly Return (%)",
                    min_value=1.0,
                    max_value=10.0,
                    value=float(self.config["STRATEGY_CONFIG"]["target_monthly_return"]) * 100,
                    step=0.1
                ) / 100
                
                leg_premium_target = st.number_input(
                    "Leg Premium Target (%)",
                    min_value=0.5,
                    max_value=5.0,
                    value=float(self.config["STRATEGY_CONFIG"]["leg_premium_target"]) * 100,
                    step=0.1
                ) / 100
                
                strangle_distance = st.number_input(
                    "Strangle Distance (points)",
                    min_value=500,
                    max_value=2000,
                    value=self.config["STRATEGY_CONFIG"]["strangle_distance"],
                    step=100
                )
                
            with col2:
                sell_expiry_weeks = st.number_input(
                    "Sell Expiry Weeks",
                    min_value=1,
                    max_value=12,
                    value=self.config["STRATEGY_CONFIG"]["sell_expiry_weeks"],
                    step=1
                )
                
                close_after_weeks = st.number_input(
                    "Close After Weeks",
                    min_value=1,
                    max_value=sell_expiry_weeks,
                    value=self.config["STRATEGY_CONFIG"]["close_after_weeks"],
                    step=1
                )
                
                hedge_expiry_weeks = st.number_input(
                    "Hedge Expiry Weeks",
                    min_value=1,
                    max_value=4,
                    value=self.config["STRATEGY_CONFIG"]["hedge_expiry_weeks"],
                    step=1
                )
                
            with col3:
                stop_loss_trigger = st.number_input(
                    "Stop Loss Trigger (%)",
                    min_value=10.0,
                    max_value=50.0,
                    value=float(self.config["STRATEGY_CONFIG"]["stop_loss_trigger"]) * 100,
                    step=5.0
                ) / 100
                
                stop_loss_percentage = st.number_input(
                    "Stop Loss Percentage (%)",
                    min_value=50.0,
                    max_value=99.0,
                    value=float(self.config["STRATEGY_CONFIG"]["stop_loss_percentage"]) * 100,
                    step=5.0
                ) / 100
                
                martingale_trigger = st.number_input(
                    "Martingale Trigger (x)",
                    min_value=1.5,
                    max_value=3.0,
                    value=float(self.config["STRATEGY_CONFIG"]["martingale_trigger"]),
                    step=0.1
                )
                
            # Trading hours configuration
            st.subheader("Trading Hours Configuration")
            
            col1, col2 = st.columns(2)
            
            with col1:
                start_time = st.time_input(
                    "Start Time",
                    datetime.datetime.strptime(self.config["TRADING_HOURS"]["start_time"], "%H:%M:%S").time()
                )
                
                check_interval = st.number_input(
                    "Check Interval (seconds)",
                    min_value=60,
                    max_value=1800,
                    value=self.config["TRADING_HOURS"]["check_interval"],
                    step=60
                )
                
            with col2:
                end_time = st.time_input(
                    "End Time",
                    datetime.datetime.strptime(self.config["TRADING_HOURS"]["end_time"], "%H:%M:%S").time()
                )
                
            # Holiday configuration
            st.subheader("Holiday Configuration")
            
            holidays = st.text_area(
                "Holidays (YYYY-MM-DD, one per line)",
                "\n".join(self.config["HOLIDAYS"])
            )
            
            # Submit button
            submitted = st.form_submit_button("Save Configuration")
            
            if submitted:
                self.logger.info("Configuration form submitted")
                try:
                    # Update configuration
                    self.config["INVESTMENT_CONFIG"]["base_investment"] = base_investment
                    self.config["INVESTMENT_CONFIG"]["lot_size"] = lot_size
                    self.config["INVESTMENT_CONFIG"]["lots_per_investment"] = lots_per_investment
                    self.config["INVESTMENT_CONFIG"]["investment_per_lot"] = investment_per_lot
                    
                    self.config["STRATEGY_CONFIG"]["target_monthly_return"] = target_monthly_return
                    self.config["STRATEGY_CONFIG"]["leg_premium_target"] = leg_premium_target
                    self.config["STRATEGY_CONFIG"]["strangle_distance"] = strangle_distance
                    self.config["STRATEGY_CONFIG"]["sell_expiry_weeks"] = sell_expiry_weeks
                    self.config["STRATEGY_CONFIG"]["close_after_weeks"] = close_after_weeks
                    self.config["STRATEGY_CONFIG"]["hedge_expiry_weeks"] = hedge_expiry_weeks
                    self.config["STRATEGY_CONFIG"]["stop_loss_trigger"] = stop_loss_trigger
                    self.config["STRATEGY_CONFIG"]["stop_loss_percentage"] = stop_loss_percentage
                    self.config["STRATEGY_CONFIG"]["martingale_trigger"] = martingale_trigger
                    
                    self.config["TRADING_HOURS"]["start_time"] = start_time.strftime("%H:%M:%S")
                    self.config["TRADING_HOURS"]["end_time"] = end_time.strftime("%H:%M:%S")
                    self.config["TRADING_HOURS"]["check_interval"] = check_interval
                    
                    self.config["HOLIDAYS"] = [h.strip() for h in holidays.split("\n") if h.strip()]
                    
                    # Save configuration to file
                    self._save_config()
                    
                    st.success("Configuration saved successfully")
                    self.logger.info("Configuration saved successfully")
                except Exception as e:
                    st.error(f"Error saving configuration: {str(e)}")
                    self.logger.error(f"Error saving configuration: {str(e)}", exc_info=True)
                
    def _render_pnl_tab(self):
        """
        Render the P&L analysis tab.
        """
        st.header("P&L Analysis")
        self.logger.debug("Rendering P&L analysis tab")
        
        try:
            # Get P&L data
            pnl_data = self._get_pnl_data()
            
            if not pnl_data:
                st.info("No P&L data available")
                self.logger.info("No P&L data available for rendering")
                return
                
            # Convert to DataFrame
            df = pd.DataFrame(pnl_data)
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)
            
            # Daily P&L chart
            st.subheader("Daily P&L")
            
            fig = px.bar(
                df,
                y="Daily P&L",
                title="Daily P&L",
                height=400
            )
            
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="P&L (₹)",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            self.logger.debug("Daily P&L chart rendered")
            
            # Cumulative P&L chart
            st.subheader("Cumulative P&L")
            
            fig = px.line(
                df,
                y="Cumulative P&L",
                title="Cumulative P&L",
                height=400
            )
            
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="P&L (₹)",
                hovermode="x unified"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            self.logger.debug("Cumulative P&L chart rendered")
            
            # P&L statistics
            st.subheader("P&L Statistics")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total P&L", f"₹{df['Cumulative P&L'].iloc[-1]:,.2f}")
                
            with col2:
                st.metric("Best Day", f"₹{df['Daily P&L'].max():,.2f}")
                
            with col3:
                st.metric("Worst Day", f"₹{df['Daily P&L'].min():,.2f}")
                
            with col4:
                roi = df['Cumulative P&L'].iloc[-1] / self.strategy.calculate_investment_amount() * 100
                st.metric("ROI", f"{roi:.2f}%")
                
            self.logger.debug("P&L statistics rendered")
            
            # P&L by option type
            st.subheader("P&L by Option Type")
            
            if "Option Type" in df.columns:
                fig = px.pie(
                    df.groupby("Option Type").sum().reset_index(),
                    values="Daily P&L",
                    names="Option Type",
                    title="P&L Distribution by Option Type",
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                self.logger.debug("P&L by option type chart rendered")
        except Exception as e:
            st.error(f"Error rendering P&L tab: {str(e)}")
            self.logger.error(f"Error rendering P&L tab: {str(e)}", exc_info=True)
            
    def _render_logs_tab(self):
        """
        Render the logs tab.
        """
        st.header("Logs and Monitoring")
        self.logger.debug("Rendering logs tab")
        
        try:
            # Create tabs for different log types
            log_tab1, log_tab2 = st.tabs(["Trading Logs", "Error Logs"])
            
            with log_tab1:
                # Display trading logs
                log_file = os.path.join("logs", self.config["LOGGING_CONFIG"]["log_file"])
                
                if os.path.exists(log_file):
                    with open(log_file, "r") as f:
                        logs = f.readlines()
                        
                    # Display the last N lines
                    log_lines = self.config["DASHBOARD_CONFIG"]["log_lines"]
                    logs = logs[-log_lines:] if len(logs) > log_lines else logs
                    
                    for log in logs:
                        st.text(log.strip())
                    
                    self.logger.debug(f"Displayed {len(logs)} trading log lines")
                else:
                    st.info(f"No trading logs available (file not found: {log_file})")
                    self.logger.warning(f"Trading log file not found: {log_file}")
                    
            with log_tab2:
                # Display error logs
                error_log_file = os.path.join("logs", self.config["LOGGING_CONFIG"]["error_log_file"])
                
                if os.path.exists(error_log_file):
                    with open(error_log_file, "r") as f:
                        error_logs = f.readlines()
                        
                    # Display the last N lines
                    error_log_lines = self.config["DASHBOARD_CONFIG"]["error_log_lines"]
                    error_logs = error_logs[-error_log_lines:] if len(error_logs) > error_log_lines else error_logs
                    
                    for log in error_logs:
                        st.text(log.strip())
                    
                    self.logger.debug(f"Displayed {len(error_logs)} error log lines")
                else:
                    st.info(f"No error logs available (file not found: {error_log_file})")
                    self.logger.warning(f"Error log file not found: {error_log_file}")
                    
            # Add refresh button
            if st.button("Refresh Logs"):
                self.logger.info("Refresh logs button clicked")
                # Use st.rerun() instead of st.experimental_rerun()
                st.rerun()
        except Exception as e:
            st.error(f"Error rendering logs tab: {str(e)}")
            self.logger.error(f"Error rendering logs tab: {str(e)}", exc_info=True)
            
    def _calculate_total_pnl(self) -> float:
        """
        Calculate total P&L across all positions.
        
        Returns:
            Total P&L
        """
        self.logger.debug("Calculating total P&L")
        total_pnl = 0.0
        
        for position in self.strategy.active_positions.values():
            total_pnl += position.pnl
            
        return total_pnl
        
    def _get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price
        """
        try:
            price = self.strategy._get_current_price(symbol) or 0.0
            self.logger.debug(f"Current price for {symbol}: {price}")
            return price
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {str(e)}")
            return 0.0
        
    def _create_payoff_diagram(self) -> go.Figure:
        """
        Create a payoff diagram for the current positions.
        
        Returns:
            Plotly figure
        """
        self.logger.debug("Creating payoff diagram")
        
        # Get current spot price
        spot_price = self.strategy._get_spot_price() or 0.0
        self.logger.debug(f"Current spot price: {spot_price}")
        
        # Create range of prices for x-axis
        price_range = np.linspace(spot_price * 0.8, spot_price * 1.2, 100)
        
        # Calculate payoff for each position at each price point
        payoffs = {}
        total_payoff = np.zeros(len(price_range))
        
        for symbol, position in self.strategy.active_positions.items():
            if position.option_type and position.strike_price:
                # Calculate option payoff
                payoff = np.zeros(len(price_range))
                
                if position.option_type.value == "CE":
                    if position.side.value == "BUY":
                        payoff = np.maximum(price_range - position.strike_price, 0) - position.average_price
                    else:  # SELL
                        payoff = position.average_price - np.maximum(price_range - position.strike_price, 0)
                else:  # PE
                    if position.side.value == "BUY":
                        payoff = np.maximum(position.strike_price - price_range, 0) - position.average_price
                    else:  # SELL
                        payoff = position.average_price - np.maximum(position.strike_price - price_range, 0)
                
                # Multiply by quantity
                payoff *= position.quantity
                
                # Add to total payoff
                total_payoff += payoff
                
                # Store for individual position lines
                payoffs[symbol] = payoff
                
        # Create figure
        fig = go.Figure()
        
        # Add individual position lines
        for symbol, payoff in payoffs.items():
            position = self.strategy.active_positions[symbol]
            name = f"{symbol} ({position.side.value} {position.option_type.value if position.option_type else ''})"
            
            fig.add_trace(go.Scatter(
                x=price_range,
                y=payoff,
                name=name,
                line=dict(width=1, dash="dot"),
                opacity=0.7
            ))
            
        # Add total payoff line
        fig.add_trace(go.Scatter(
            x=price_range,
            y=total_payoff,
            name="Total Payoff",
            line=dict(width=3, color="black")
        ))
        
        # Add horizontal line at y=0
        fig.add_shape(
            type="line",
            x0=price_range[0],
            y0=0,
            x1=price_range[-1],
            y1=0,
            line=dict(color="gray", width=1, dash="dash")
        )
        
        # Add vertical line at current spot price
        fig.add_shape(
            type="line",
            x0=spot_price,
            y0=min(total_payoff) - 1000,
            x1=spot_price,
            y1=max(total_payoff) + 1000,
            line=dict(color="red", width=1, dash="dash")
        )
        
        # Update layout
        fig.update_layout(
            title="Position Payoff at Expiry",
            xaxis_title="Nifty Price",
            yaxis_title="P&L (₹)",
            hovermode="x unified",
            height=500
        )
        
        self.logger.debug("Payoff diagram created successfully")
        return fig
        
    def _get_pnl_data(self) -> List[Dict[str, Any]]:
        """
        Get P&L data for analysis.
        
        Returns:
            List of P&L data points
        """
        self.logger.debug("Getting P&L data")
        
        # Check if P&L data file exists
        pnl_file = "pnl_data.json"
        
        if os.path.exists(pnl_file):
            self.logger.debug(f"Loading P&L data from file: {pnl_file}")
            try:
                with open(pnl_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading P&L data from file: {str(e)}")
                # Fall back to generating sample data
                pass
                
        # If not, generate sample data
        self.logger.debug("Generating sample P&L data")
        start_date = datetime.date.today() - datetime.timedelta(days=30)
        data = []
        
        cumulative_pnl = 0.0
        
        for i in range(30):
            date = start_date + datetime.timedelta(days=i)
            
            # Skip weekends
            if date.weekday() >= 5:
                continue
                
            # Generate random daily P&L
            daily_pnl = np.random.normal(1000, 2000)
            cumulative_pnl += daily_pnl
            
            data.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Daily P&L": daily_pnl,
                "Cumulative P&L": cumulative_pnl,
                "Option Type": "CE" if np.random.random() > 0.5 else "PE"
            })
            
        return data
        
    def _save_config(self):
        """
        Save configuration to file.
        """
        self.logger.info("Saving configuration to file")
        
        # Convert config to JSON-serializable format
        config_json = {}
        
        for section, values in self.config.items():
            if isinstance(values, dict):
                config_json[section] = {}
                for key, value in values.items():
                    config_json[section][key] = value
            else:
                config_json[section] = values
                
        # Save to file
        config_file = "config.json"
        self.logger.debug(f"Writing configuration to {config_file}")
        try:
            with open(config_file, "w") as f:
                json.dump(config_json, f, indent=4)
                
            # Update strategy config
            self.strategy.config = self.config
            self.logger.info(f"Configuration saved successfully to {config_file}")
        except Exception as e:
            self.logger.error(f"Error saving configuration to file: {str(e)}", exc_info=True)
            raise

# Function to run Streamlit in a separate thread for Colab compatibility
def run_streamlit_in_thread(dashboard):
    """
    Run Streamlit dashboard in a separate thread.
    This helps address the "mainthread missing scriptruncontext" warning in Colab.
    
    Args:
        dashboard: StreamlitDashboard instance
    """
    logger.info("Starting Streamlit dashboard in separate thread")
    dashboard.run()
