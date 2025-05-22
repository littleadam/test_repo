"""
Iron Condor Options Trading Strategy implementation.
Handles the core trading logic for the iron condor strategy.
"""

import datetime
import logging
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple

from models import Order, OrderType, OrderSide, OrderStatus, ProductType, OptionType, Position, OptionContract, OptionChain
from date_utils import get_expiry_date_n_weeks_ahead, is_trading_day, get_next_trading_day

class IronCondorStrategy:
    """
    Implementation of the Iron Condor Options Trading Strategy.
    """
    
    def __init__(self, api, config):
        """
        Initialize the strategy.
        
        Args:
            api: API client instance
            config: Configuration dictionary
        """
        self.api = api
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.logger.info("Iron Condor Strategy initialized")
        self.active_positions = {}  # Symbol -> Position
        self.active_orders = {}  # Order ID -> Order
        self.option_chains = {}  # Expiry date -> OptionChain
        
    def initialize(self) -> bool:
        """
        Initialize the strategy.
        
        Returns:
            True if initialization successful, False otherwise
        """
        self.logger.info("Initializing Iron Condor Strategy")
        try:
            # Login to API
            self.logger.info("Logging in to API")
            if not self.api.login():
                self.logger.error("Failed to login to API")
                return False
                
            # Update positions
            self.logger.info("Updating positions")
            self._update_positions()
            
            self.logger.info("Strategy initialization successful")
            return True
        except Exception as e:
            self.logger.error(f"Strategy initialization error: {str(e)}", exc_info=True)
            return False
            
    def calculate_investment_amount(self) -> float:
        """
        Calculate the total investment amount.
        
        Returns:
            Total investment amount
        """
        self.logger.debug("Calculating investment amount")
        try:
            # Get fund summary from API
            fund_summary = self.api.get_fund_summary()
            if fund_summary:
                # Extract available funds
                available_funds = float(fund_summary.get("availableFunds", 0))
                self.logger.debug(f"Available funds from API: {available_funds}")
                return available_funds
            else:
                # Use default from config if API call fails
                base_investment = self.config["INVESTMENT_CONFIG"]["base_investment"]
                self.logger.debug(f"Using default base investment: {base_investment}")
                return base_investment
        except Exception as e:
            self.logger.error(f"Error calculating investment amount: {str(e)}", exc_info=True)
            # Use default from config if calculation fails
            base_investment = self.config["INVESTMENT_CONFIG"]["base_investment"]
            self.logger.debug(f"Using default base investment due to error: {base_investment}")
            return base_investment
            
    def _update_positions(self):
        """
        Update active positions from API.
        """
        self.logger.info("Updating active positions")
        try:
            # Get positions from API
            positions_data = self.api.get_positions()
            if not positions_data:
                self.logger.warning("No positions data received from API")
                return
                
            # Clear existing positions
            self.active_positions = {}
            
            # Process positions
            for position_data in positions_data:
                position = Position.from_api_response(position_data)
                self.active_positions[position.symbol] = position
                
            self.logger.info(f"Updated {len(self.active_positions)} active positions")
            
            # Update P&L for each position
            self._update_position_pnl()
        except Exception as e:
            self.logger.error(f"Error updating positions: {str(e)}", exc_info=True)
            
    def _update_position_pnl(self):
        """
        Update P&L for each position.
        """
        self.logger.debug("Updating position P&L")
        try:
            for symbol, position in self.active_positions.items():
                current_price = self._get_current_price(symbol)
                if current_price is None:
                    self.logger.warning(f"Failed to get current price for {symbol}")
                    continue
                    
                # Calculate P&L
                if position.side == OrderSide.BUY:
                    position.pnl = (current_price - position.average_price) * position.quantity
                else:  # SELL
                    position.pnl = (position.average_price - current_price) * position.quantity
                    
                self.logger.debug(f"Updated P&L for {symbol}: {position.pnl}")
        except Exception as e:
            self.logger.error(f"Error updating position P&L: {str(e)}", exc_info=True)
            
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None if not available
        """
        self.logger.debug(f"Getting current price for {symbol}")
        try:
            quote = self.api.get_quote(symbol)
            if quote:
                price = float(quote.get("lastPrice", 0))
                self.logger.debug(f"Current price for {symbol}: {price}")
                return price
            else:
                self.logger.warning(f"Failed to get quote for {symbol}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {str(e)}", exc_info=True)
            return None
            
    def _get_spot_price(self) -> Optional[float]:
        """
        Get current spot price for Nifty.
        
        Returns:
            Spot price or None if not available
        """
        self.logger.debug("Getting Nifty spot price")
        try:
            # Get quote for Nifty
            quote = self.api.get_quote("NIFTY")
            if quote:
                price = float(quote.get("lastPrice", 0))
                self.logger.debug(f"Nifty spot price: {price}")
                return price
            else:
                self.logger.warning("Failed to get Nifty spot price")
                return None
        except Exception as e:
            self.logger.error(f"Error getting Nifty spot price: {str(e)}", exc_info=True)
            return None
            
    def get_option_chain_for_expiry(self, expiry_date: datetime.date) -> Optional[OptionChain]:
        """
        Get option chain for a specific expiry date.
        
        Args:
            expiry_date: Expiry date
            
        Returns:
            Option chain or None if not available
        """
        self.logger.debug(f"Getting option chain for expiry {expiry_date}")
        try:
            # Check if we already have this option chain
            if expiry_date in self.option_chains:
                self.logger.debug(f"Using cached option chain for {expiry_date}")
                return self.option_chains[expiry_date]
                
            # Get option chain master
            option_chain_master = self.api.get_option_chain_master()
            if not option_chain_master:
                self.logger.warning("Failed to get option chain master")
                return None
                
            # Find the expiry timestamp
            expiry_timestamp = None
            for expiry in option_chain_master.get("expiryDates", []):
                expiry_date_str = expiry.get("expiryDate")
                if expiry_date_str:
                    expiry_date_obj = datetime.datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
                    if expiry_date_obj == expiry_date:
                        expiry_timestamp = expiry.get("timestamp")
                        break
                        
            if not expiry_timestamp:
                self.logger.warning(f"Expiry date {expiry_date} not found in option chain master")
                return None
                
            # Get option chain for this expiry
            token = option_chain_master.get("token")
            if not token:
                self.logger.warning("Token not found in option chain master")
                return None
                
            option_chain_data = self.api.get_option_chain(expiry_timestamp, token)
            if not option_chain_data:
                self.logger.warning(f"Failed to get option chain for expiry {expiry_date}")
                return None
                
            # Create option chain object
            expiry_datetime = datetime.datetime.combine(expiry_date, datetime.time(15, 30))
            option_chain = OptionChain.from_api_response(option_chain_data, expiry_datetime)
            
            # Cache the option chain
            self.option_chains[expiry_date] = option_chain
            
            self.logger.debug(f"Option chain for {expiry_date} fetched successfully")
            return option_chain
        except Exception as e:
            self.logger.error(f"Error getting option chain for expiry {expiry_date}: {str(e)}", exc_info=True)
            return None
            
    def place_short_strangle(self, investment_amount: float, spot_price: float) -> bool:
        """
        Place a short strangle position.
        
        Args:
            investment_amount: Investment amount
            spot_price: Current spot price
            
        Returns:
            True if successful, False otherwise
        """
        self.logger.info(f"Placing short strangle with investment amount {investment_amount}, spot price {spot_price}")
        try:
            # Calculate lot size and quantity
            lot_size = self.config["INVESTMENT_CONFIG"]["lot_size"]
            lots_per_investment = self.config["INVESTMENT_CONFIG"]["lots_per_investment"]
            quantity = lot_size * lots_per_investment
            
            # Calculate strike prices
            strangle_distance = self.config["STRATEGY_CONFIG"]["strangle_distance"]
            ce_strike = int(spot_price + strangle_distance)
            pe_strike = int(spot_price - strangle_distance)
            
            # Round to nearest strike
            ce_strike = round(ce_strike / 50) * 50
            pe_strike = round(pe_strike / 50) * 50
            
            self.logger.info(f"Calculated strike prices: CE {ce_strike}, PE {pe_strike}")
            
            # Get expiry dates
            sell_expiry_date = get_expiry_date_n_weeks_ahead(self.config["STRATEGY_CONFIG"]["sell_expiry_weeks"])
            hedge_expiry_date = get_expiry_date_n_weeks_ahead(self.config["STRATEGY_CONFIG"]["hedge_expiry_weeks"])
            
            if not sell_expiry_date or not hedge_expiry_date:
                self.logger.error("Failed to calculate expiry dates")
                return False
                
            self.logger.info(f"Expiry dates: Sell {sell_expiry_date}, Hedge {hedge_expiry_date}")
            
            # Get option chains
            sell_option_chain = self.get_option_chain_for_expiry(sell_expiry_date)
            hedge_option_chain = self.get_option_chain_for_expiry(hedge_expiry_date)
            
            if not sell_option_chain or not hedge_option_chain:
                self.logger.error("Failed to get option chains")
                return False
                
            # Place sell orders
            self.logger.info("Placing sell orders")
            ce_sell_order = self._place_sell_order(
                sell_option_chain,
                ce_strike,
                OptionType.CE,
                quantity
            )
            
            pe_sell_order = self._place_sell_order(
                sell_option_chain,
                pe_strike,
                OptionType.PE,
                quantity
            )
            
            if not ce_sell_order or not pe_sell_order:
                self.logger.error("Failed to place sell orders")
                return False
                
            # Place hedge orders
            self.logger.info("Placing hedge orders")
            ce_hedge_order = self._place_hedge_order(
                hedge_option_chain,
                ce_strike,
                OptionType.CE,
                quantity
            )
            
            pe_hedge_order = self._place_hedge_order(
                hedge_option_chain,
                pe_strike,
                OptionType.PE,
                quantity
            )
            
            if not ce_hedge_order or not pe_hedge_order:
                self.logger.error("Failed to place hedge orders")
                return False
                
            self.logger.info("Short strangle placed successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error placing short strangle: {str(e)}", exc_info=True)
            return False
            
    def _place_sell_order(self, option_chain: OptionChain, strike: int, option_type: OptionType, quantity: int) -> Optional[Order]:
        """
        Place a sell order.
        
        Args:
            option_chain: Option chain
            strike: Strike price
            option_type: Option type (CE/PE)
            quantity: Quantity
            
        Returns:
            Order object or None if failed
        """
        self.logger.debug(f"Placing sell order: Strike {strike}, Type {option_type.value}, Quantity {quantity}")
        try:
            # Get contract
            if strike not in option_chain.contracts:
                self.logger.warning(f"Strike {strike} not found in option chain")
                return None
                
            if option_type.value not in option_chain.contracts[strike]:
                self.logger.warning(f"Option type {option_type.value} not found for strike {strike}")
                return None
                
            contract = option_chain.contracts[strike][option_type.value]
            
            # Check premium
            premium = contract.last_price
            leg_premium_target = self.config["STRATEGY_CONFIG"]["leg_premium_target"]
            investment_per_lot = self.config["INVESTMENT_CONFIG"]["investment_per_lot"]
            target_premium = investment_per_lot * leg_premium_target
            
            self.logger.debug(f"Premium: {premium}, Target: {target_premium}")
            
            # Place order
            order_params = {
                "trading_symbol": contract.symbol,
                "exchange": "NSE",
                "transaction_type": "SELL",
                "order_type": "MARKET",
                "quantity": quantity,
                "product": "NRML",
                "price": 0  # Market order
            }
            
            self.logger.debug(f"Placing sell order with params: {order_params}")
            order_response = self.api.place_order(order_params)
            
            if not order_response:
                self.logger.warning("Failed to place sell order")
                return None
                
            # Create order object
            order = Order(
                symbol=contract.symbol,
                exchange="NSE",
                order_type=OrderType.MARKET,
                side=OrderSide.SELL,
                quantity=quantity,
                product=ProductType.NRML,
                price=premium,
                option_type=option_type,
                strike_price=strike,
                expiry_date=option_chain.expiry_date,
                order_id=order_response.get("orderId")
            )
            
            # Add to active orders
            if order.order_id:
                self.active_orders[order.order_id] = order
                
            self.logger.info(f"Sell order placed successfully: {order.symbol}, Order ID: {order.order_id}")
            return order
        except Exception as e:
            self.logger.error(f"Error placing sell order: {str(e)}", exc_info=True)
            return None
            
    def _place_hedge_order(self, option_chain: OptionChain, sell_strike: int, option_type: OptionType, quantity: int) -> Optional[Order]:
        """
        Place a hedge order.
        
        Args:
            option_chain: Option chain
            sell_strike: Strike price of the sell order
            option_type: Option type (CE/PE)
            quantity: Quantity
            
        Returns:
            Order object or None if failed
        """
        self.logger.debug(f"Placing hedge order for sell strike {sell_strike}, Type {option_type.value}, Quantity {quantity}")
        try:
            # Calculate hedge strike
            # For CE, hedge strike is one strike above sell strike
            # For PE, hedge strike is one strike below sell strike
            if option_type == OptionType.CE:
                hedge_strike = sell_strike + 50
            else:  # PE
                hedge_strike = sell_strike - 50
                
            self.logger.debug(f"Calculated hedge strike: {hedge_strike}")
            
            # Get contract
            if hedge_strike not in option_chain.contracts:
                self.logger.warning(f"Hedge strike {hedge_strike} not found in option chain")
                return None
                
            if option_type.value not in option_chain.contracts[hedge_strike]:
                self.logger.warning(f"Option type {option_type.value} not found for hedge strike {hedge_strike}")
                return None
                
            contract = option_chain.contracts[hedge_strike][option_type.value]
            
            # Place order
            order_params = {
                "trading_symbol": contract.symbol,
                "exchange": "NSE",
                "transaction_type": "BUY",
                "order_type": "MARKET",
                "quantity": quantity,
                "product": "NRML",
                "price": 0  # Market order
            }
            
            self.logger.debug(f"Placing hedge order with params: {order_params}")
            order_response = self.api.place_order(order_params)
            
            if not order_response:
                self.logger.warning("Failed to place hedge order")
                return None
                
            # Create order object
            order = Order(
                symbol=contract.symbol,
                exchange="NSE",
                order_type=OrderType.MARKET,
                side=OrderSide.BUY,
                quantity=quantity,
                product=ProductType.NRML,
                price=contract.last_price,
                option_type=option_type,
                strike_price=hedge_strike,
                expiry_date=option_chain.expiry_date,
                order_id=order_response.get("orderId"),
                is_hedge=True
            )
            
            # Add to active orders
            if order.order_id:
                self.active_orders[order.order_id] = order
                
            self.logger.info(f"Hedge order placed successfully: {order.symbol}, Order ID: {order.order_id}")
            return order
        except Exception as e:
            self.logger.error(f"Error placing hedge order: {str(e)}", exc_info=True)
            return None
            
    def handle_stop_loss(self, position: Position, current_price: float) -> bool:
        """
        Handle stop loss for a position.
        
        Args:
            position: Position
            current_price: Current price
            
        Returns:
            True if stop loss handled, False otherwise
        """
        self.logger.debug(f"Handling stop loss for {position.symbol}")
        try:
            # Check if stop loss is triggered
            stop_loss_trigger = self.config["STRATEGY_CONFIG"]["stop_loss_trigger"]
            stop_loss_percentage = self.config["STRATEGY_CONFIG"]["stop_loss_percentage"]
            
            # For sell positions, stop loss is triggered when price drops by stop_loss_trigger
            if position.side == OrderSide.SELL:
                price_drop = (position.average_price - current_price) / position.average_price
                
                if price_drop >= stop_loss_trigger:
                    self.logger.info(f"Stop loss triggered for {position.symbol}: Price drop {price_drop:.2%}")
                    
                    # Place stop loss order
                    stop_loss_price = position.average_price * stop_loss_percentage
                    
                    order_params = {
                        "trading_symbol": position.symbol,
                        "exchange": position.exchange,
                        "transaction_type": "BUY",  # Buy to close sell position
                        "order_type": "SL",
                        "quantity": position.quantity,
                        "product": position.product.value,
                        "price": stop_loss_price,
                        "trigger_price": stop_loss_price
                    }
                    
                    self.logger.debug(f"Placing stop loss order with params: {order_params}")
                    order_response = self.api.place_order(order_params)
                    
                    if not order_response:
                        self.logger.warning(f"Failed to place stop loss order for {position.symbol}")
                        return False
                        
                    # Create order object
                    order = Order(
                        symbol=position.symbol,
                        exchange=position.exchange,
                        order_type=OrderType.SL,
                        side=OrderSide.BUY,
                        quantity=position.quantity,
                        product=position.product,
                        price=stop_loss_price,
                        trigger_price=stop_loss_price,
                        option_type=position.option_type,
                        strike_price=position.strike_price,
                        expiry_date=position.expiry_date,
                        order_id=order_response.get("orderId")
                    )
                    
                    # Add to active orders
                    if order.order_id:
                        self.active_orders[order.order_id] = order
                        
                    self.logger.info(f"Stop loss order placed for {position.symbol}, Order ID: {order.order_id}")
                    
                    # Place new sell order at the same strike and expiry
                    self.logger.info(f"Placing new sell order for {position.symbol}")
                    
                    # Get option chain
                    if position.expiry_date and position.expiry_date.date():
                        option_chain = self.get_option_chain_for_expiry(position.expiry_date.date())
                        
                        if option_chain and position.strike_price and position.option_type:
                            new_sell_order = self._place_sell_order(
                                option_chain,
                                position.strike_price,
                                position.option_type,
                                position.quantity
                            )
                            
                            if new_sell_order:
                                self.logger.info(f"New sell order placed successfully: {new_sell_order.symbol}, Order ID: {new_sell_order.order_id}")
                            else:
                                self.logger.warning(f"Failed to place new sell order for {position.symbol}")
                        else:
                            self.logger.warning(f"Failed to get option chain or position details for {position.symbol}")
                    else:
                        self.logger.warning(f"Missing expiry date for {position.symbol}")
                        
                    return True
                    
            return False
        except Exception as e:
            self.logger.error(f"Error handling stop loss for {position.symbol}: {str(e)}", exc_info=True)
            return False
            
    def handle_martingale(self, position: Position, current_price: float, option_chain: OptionChain) -> bool:
        """
        Handle martingale for a position.
        
        Args:
            position: Position
            current_price: Current price
            option_chain: Option chain
            
        Returns:
            True if martingale handled, False otherwise
        """
        self.logger.debug(f"Handling martingale for {position.symbol}")
        try:
            # Check if martingale is triggered
            martingale_trigger = self.config["STRATEGY_CONFIG"]["martingale_trigger"]
            
            # For sell positions, martingale is triggered when price increases by martingale_trigger
            if position.side == OrderSide.SELL:
                price_increase = current_price / position.average_price
                
                if price_increase >= martingale_trigger:
                    self.logger.info(f"Martingale triggered for {position.symbol}: Price increase {price_increase:.2f}x")
                    
                    # Place martingale buy order at the next strike
                    if position.strike_price and position.option_type:
                        # Calculate martingale strike
                        if position.option_type == OptionType.CE:
                            martingale_strike = position.strike_price + 50
                        else:  # PE
                            martingale_strike = position.strike_price - 50
                            
                        self.logger.debug(f"Calculated martingale strike: {martingale_strike}")
                        
                        # Get contract
                        if martingale_strike in option_chain.contracts and position.option_type.value in option_chain.contracts[martingale_strike]:
                            contract = option_chain.contracts[martingale_strike][position.option_type.value]
                            
                            # Place buy order
                            order_params = {
                                "trading_symbol": contract.symbol,
                                "exchange": position.exchange,
                                "transaction_type": "BUY",
                                "order_type": "MARKET",
                                "quantity": position.quantity,
                                "product": position.product.value,
                                "price": 0  # Market order
                            }
                            
                            self.logger.debug(f"Placing martingale buy order with params: {order_params}")
                            order_response = self.api.place_order(order_params)
                            
                            if not order_response:
                                self.logger.warning(f"Failed to place martingale buy order for {position.symbol}")
                                return False
                                
                            # Create order object
                            buy_order = Order(
                                symbol=contract.symbol,
                                exchange=position.exchange,
                                order_type=OrderType.MARKET,
                                side=OrderSide.BUY,
                                quantity=position.quantity,
                                product=position.product,
                                price=contract.last_price,
                                option_type=position.option_type,
                                strike_price=martingale_strike,
                                expiry_date=position.expiry_date,
                                order_id=order_response.get("orderId"),
                                is_martingale=True
                            )
                            
                            # Add to active orders
                            if buy_order.order_id:
                                self.active_orders[buy_order.order_id] = buy_order
                                
                            self.logger.info(f"Martingale buy order placed for {contract.symbol}, Order ID: {buy_order.order_id}")
                            
                            # Place new sell orders with double quantity and half premium
                            martingale_quantity_multiplier = self.config["STRATEGY_CONFIG"]["martingale_quantity_multiplier"]
                            martingale_premium_divisor = self.config["STRATEGY_CONFIG"]["martingale_premium_divisor"]
                            
                            target_premium = contract.last_price / martingale_premium_divisor
                            new_quantity = int(position.quantity * martingale_quantity_multiplier)
                            
                            self.logger.debug(f"Martingale sell parameters: Target premium {target_premium}, New quantity {new_quantity}")
                            
                            # Find strikes with premium close to target
                            sell_strikes = []
                            
                            for strike in option_chain.contracts:
                                if position.option_type.value in option_chain.contracts[strike]:
                                    contract_premium = option_chain.contracts[strike][position.option_type.value].last_price
                                    
                                    # Check if premium is close to target
                                    if 0.8 * target_premium <= contract_premium <= 1.2 * target_premium:
                                        sell_strikes.append(strike)
                                        
                            self.logger.debug(f"Found {len(sell_strikes)} potential sell strikes: {sell_strikes}")
                            
                            # Place sell orders
                            for strike in sell_strikes:
                                contract = option_chain.contracts[strike][position.option_type.value]
                                
                                order_params = {
                                    "trading_symbol": contract.symbol,
                                    "exchange": position.exchange,
                                    "transaction_type": "SELL",
                                    "order_type": "MARKET",
                                    "quantity": new_quantity,
                                    "product": position.product.value,
                                    "price": 0  # Market order
                                }
                                
                                self.logger.debug(f"Placing martingale sell order with params: {order_params}")
                                order_response = self.api.place_order(order_params)
                                
                                if not order_response:
                                    self.logger.warning(f"Failed to place martingale sell order for strike {strike}")
                                    continue
                                    
                                # Create order object
                                sell_order = Order(
                                    symbol=contract.symbol,
                                    exchange=position.exchange,
                                    order_type=OrderType.MARKET,
                                    side=OrderSide.SELL,
                                    quantity=new_quantity,
                                    product=position.product,
                                    price=contract.last_price,
                                    option_type=position.option_type,
                                    strike_price=strike,
                                    expiry_date=position.expiry_date,
                                    order_id=order_response.get("orderId"),
                                    is_martingale=True
                                )
                                
                                # Add to active orders
                                if sell_order.order_id:
                                    self.active_orders[sell_order.order_id] = sell_order
                                    
                                self.logger.info(f"Martingale sell order placed for {contract.symbol}, Order ID: {sell_order.order_id}")
                                
                            return True
                        else:
                            self.logger.warning(f"Martingale strike {martingale_strike} or option type {position.option_type.value} not found in option chain")
                    else:
                        self.logger.warning(f"Missing strike price or option type for {position.symbol}")
                        
            return False
        except Exception as e:
            self.logger.error(f"Error handling martingale for {position.symbol}: {str(e)}", exc_info=True)
            return False
            
    def close_positions_at_expiry(self) -> bool:
        """
        Close positions at expiry.
        
        Returns:
            True if positions closed, False otherwise
        """
        self.logger.info("Checking positions for expiry")
        try:
            today = datetime.date.today()
            close_after_weeks = self.config["STRATEGY_CONFIG"]["close_after_weeks"]
            close_date = get_expiry_date_n_weeks_ahead(close_after_weeks)
            
            if not close_date:
                self.logger.warning("Failed to calculate close date")
                return False
                
            self.logger.debug(f"Close date: {close_date}")
            
            # Check if any positions need to be closed
            positions_to_close = []
            
            for symbol, position in self.active_positions.items():
                if position.expiry_date and position.expiry_date.date() <= close_date:
                    positions_to_close.append(position)
                    
            if not positions_to_close:
                self.logger.info("No positions to close at expiry")
                return False
                
            self.logger.info(f"Closing {len(positions_to_close)} positions at expiry")
            
            # Close positions
            for position in positions_to_close:
                order_params = {
                    "trading_symbol": position.symbol,
                    "exchange": position.exchange,
                    "transaction_type": "BUY" if position.side == OrderSide.SELL else "SELL",
                    "order_type": "MARKET",
                    "quantity": position.quantity,
                    "product": position.product.value,
                    "price": 0  # Market order
                }
                
                self.logger.debug(f"Placing close order with params: {order_params}")
                order_response = self.api.place_order(order_params)
                
                if not order_response:
                    self.logger.warning(f"Failed to close position for {position.symbol}")
                    continue
                    
                self.logger.info(f"Closed position for {position.symbol}")
                
            # Update positions
            self._update_positions()
            
            return True
        except Exception as e:
            self.logger.error(f"Error closing positions at expiry: {str(e)}", exc_info=True)
            return False
            
    def roll_hedge_positions(self) -> bool:
        """
        Roll hedge positions to the next expiry.
        
        Returns:
            True if hedges rolled, False otherwise
        """
        self.logger.info("Checking hedge positions for rolling")
        try:
            today = datetime.date.today()
            
            # Check if any hedge positions need to be rolled
            hedge_positions = []
            
            for symbol, position in self.active_positions.items():
                if position.is_hedge and position.expiry_date and position.expiry_date.date() <= today:
                    hedge_positions.append(position)
                    
            if not hedge_positions:
                self.logger.info("No hedge positions to roll")
                return False
                
            self.logger.info(f"Rolling {len(hedge_positions)} hedge positions")
            
            # Get new expiry date
            hedge_expiry_date = get_expiry_date_n_weeks_ahead(self.config["STRATEGY_CONFIG"]["hedge_expiry_weeks"])
            
            if not hedge_expiry_date:
                self.logger.warning("Failed to calculate hedge expiry date")
                return False
                
            self.logger.debug(f"New hedge expiry date: {hedge_expiry_date}")
            
            # Get option chain
            option_chain = self.get_option_chain_for_expiry(hedge_expiry_date)
            
            if not option_chain:
                self.logger.warning("Failed to get option chain for hedge expiry")
                return False
                
            # Close old hedge positions and place new ones
            for position in hedge_positions:
                # Close old position
                order_params = {
                    "trading_symbol": position.symbol,
                    "exchange": position.exchange,
                    "transaction_type": "SELL",  # Sell to close buy position
                    "order_type": "MARKET",
                    "quantity": position.quantity,
                    "product": position.product.value,
                    "price": 0  # Market order
                }
                
                self.logger.debug(f"Placing close order for old hedge with params: {order_params}")
                order_response = self.api.place_order(order_params)
                
                if not order_response:
                    self.logger.warning(f"Failed to close hedge position for {position.symbol}")
                    continue
                    
                self.logger.info(f"Closed hedge position for {position.symbol}")
                
                # Place new hedge order
                if position.strike_price and position.option_type:
                    new_hedge_order = self._place_hedge_order(
                        option_chain,
                        position.strike_price,
                        position.option_type,
                        position.quantity
                    )
                    
                    if new_hedge_order:
                        self.logger.info(f"New hedge order placed successfully: {new_hedge_order.symbol}, Order ID: {new_hedge_order.order_id}")
                    else:
                        self.logger.warning(f"Failed to place new hedge order for {position.symbol}")
                else:
                    self.logger.warning(f"Missing strike price or option type for {position.symbol}")
                    
            # Update positions
            self._update_positions()
            
            return True
        except Exception as e:
            self.logger.error(f"Error rolling hedge positions: {str(e)}", exc_info=True)
            return False
