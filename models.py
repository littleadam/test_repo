"""
Models for representing orders, positions, and option contracts.
"""

from dataclasses import dataclass
from enum import Enum
import datetime
from typing import Dict, Any, Optional, List

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    SL_M = "SL-M"

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(str, Enum):
    PENDING = "PENDING"
    OPEN = "OPEN"
    COMPLETE = "COMPLETE"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"

class ProductType(str, Enum):
    NRML = "NRML"
    MIS = "MIS"
    CNC = "CNC"

class OptionType(str, Enum):
    CE = "CE"
    PE = "PE"

@dataclass
class Order:
    """
    Represents an order in the trading system.
    """
    symbol: str
    exchange: str
    order_type: OrderType
    side: OrderSide
    quantity: int
    product: ProductType
    price: float = 0.0
    trigger_price: float = 0.0
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    option_type: Optional[OptionType] = None
    strike_price: Optional[int] = None
    expiry_date: Optional[datetime.datetime] = None
    is_hedge: bool = False
    is_martingale: bool = False
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Order':
        """
        Create an Order object from API response.
        
        Args:
            data: Order data from API
            
        Returns:
            Order object
        """
        return cls(
            symbol=data.get("tradingSymbol", ""),
            exchange=data.get("exchange", ""),
            order_type=OrderType(data.get("orderType", "MARKET")),
            side=OrderSide(data.get("transactionType", "BUY")),
            quantity=int(data.get("quantity", 0)),
            product=ProductType(data.get("product", "NRML")),
            price=float(data.get("price", 0.0)),
            trigger_price=float(data.get("triggerPrice", 0.0)),
            order_id=data.get("orderId", None),
            status=OrderStatus(data.get("status", "PENDING")),
            # Extract option type from symbol if available
            option_type=OptionType.CE if data.get("tradingSymbol", "").endswith("CE") else 
                       OptionType.PE if data.get("tradingSymbol", "").endswith("PE") else None,
            # Extract strike price from symbol if available
            strike_price=cls._extract_strike_from_symbol(data.get("tradingSymbol", "")),
            # Extract expiry date from symbol if available
            expiry_date=cls._extract_expiry_from_symbol(data.get("tradingSymbol", ""))
        )
    
    @staticmethod
    def _extract_strike_from_symbol(symbol: str) -> Optional[int]:
        """
        Extract strike price from symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Strike price or None if not found
        """
        # Implementation depends on symbol format
        # This is a placeholder
        try:
            # Assuming format like NIFTY21JUN15000CE
            # Extract the numeric part before CE/PE
            if symbol.endswith("CE") or symbol.endswith("PE"):
                # Find the last digit in the symbol before CE/PE
                for i in range(len(symbol) - 2, -1, -1):
                    if not symbol[i].isdigit():
                        return int(symbol[i+1:-2])
        except:
            pass
        return None
    
    @staticmethod
    def _extract_expiry_from_symbol(symbol: str) -> Optional[datetime.datetime]:
        """
        Extract expiry date from symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Expiry date or None if not found
        """
        # Implementation depends on symbol format
        # This is a placeholder
        try:
            # Assuming format like NIFTY21JUN15000CE
            # Extract the date part
            if symbol.startswith("NIFTY"):
                year = 2000 + int(symbol[5:7])
                month_str = symbol[7:10]
                month_map = {
                    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
                }
                month = month_map.get(month_str.upper(), 1)
                return datetime.datetime(year, month, 15, 15, 30)  # Assuming expiry at 15:30
        except:
            pass
        return None

@dataclass
class Position:
    """
    Represents a position in the trading system.
    """
    symbol: str
    exchange: str
    quantity: int
    average_price: float
    side: OrderSide
    product: ProductType
    option_type: Optional[OptionType] = None
    strike_price: Optional[int] = None
    expiry_date: Optional[datetime.datetime] = None
    is_hedge: bool = False
    is_martingale: bool = False
    pnl: float = 0.0
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> 'Position':
        """
        Create a Position object from API response.
        
        Args:
            data: Position data from API
            
        Returns:
            Position object
        """
        side = OrderSide.BUY if int(data.get("netQuantity", 0)) > 0 else OrderSide.SELL
        return cls(
            symbol=data.get("tradingSymbol", ""),
            exchange=data.get("exchange", ""),
            quantity=abs(int(data.get("netQuantity", 0))),
            average_price=float(data.get("averagePrice", 0.0)),
            side=side,
            product=ProductType(data.get("product", "NRML")),
            # Extract option type from symbol if available
            option_type=OptionType.CE if data.get("tradingSymbol", "").endswith("CE") else 
                       OptionType.PE if data.get("tradingSymbol", "").endswith("PE") else None,
            # Extract strike price from symbol if available
            strike_price=cls._extract_strike_from_symbol(data.get("tradingSymbol", "")),
            # Extract expiry date from symbol if available
            expiry_date=cls._extract_expiry_from_symbol(data.get("tradingSymbol", "")),
            pnl=float(data.get("pnl", 0.0))
        )
    
    @staticmethod
    def _extract_strike_from_symbol(symbol: str) -> Optional[int]:
        """
        Extract strike price from symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Strike price or None if not found
        """
        # Implementation depends on symbol format
        # This is a placeholder
        try:
            # Assuming format like NIFTY21JUN15000CE
            # Extract the numeric part before CE/PE
            if symbol.endswith("CE") or symbol.endswith("PE"):
                # Find the last digit in the symbol before CE/PE
                for i in range(len(symbol) - 2, -1, -1):
                    if not symbol[i].isdigit():
                        return int(symbol[i+1:-2])
        except:
            pass
        return None
    
    @staticmethod
    def _extract_expiry_from_symbol(symbol: str) -> Optional[datetime.datetime]:
        """
        Extract expiry date from symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Expiry date or None if not found
        """
        # Implementation depends on symbol format
        # This is a placeholder
        try:
            # Assuming format like NIFTY21JUN15000CE
            # Extract the date part
            if symbol.startswith("NIFTY"):
                year = 2000 + int(symbol[5:7])
                month_str = symbol[7:10]
                month_map = {
                    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
                }
                month = month_map.get(month_str.upper(), 1)
                return datetime.datetime(year, month, 15, 15, 30)  # Assuming expiry at 15:30
        except:
            pass
        return None

@dataclass
class OptionContract:
    """
    Represents an option contract.
    """
    symbol: str
    strike_price: int
    option_type: OptionType
    expiry_date: datetime.datetime
    last_price: float
    change_percent: float
    volume: int
    open_interest: int
    bid_price: float
    ask_price: float
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any], expiry_date: datetime.datetime) -> 'OptionContract':
        """
        Create an OptionContract object from API response.
        
        Args:
            data: Option contract data from API
            expiry_date: Expiry date
            
        Returns:
            OptionContract object
        """
        return cls(
            symbol=data.get("tradingSymbol", ""),
            strike_price=int(data.get("strikePrice", 0)),
            option_type=OptionType.CE if data.get("optionType", "") == "CE" else OptionType.PE,
            expiry_date=expiry_date,
            last_price=float(data.get("lastPrice", 0.0)),
            change_percent=float(data.get("changePercent", 0.0)),
            volume=int(data.get("volume", 0)),
            open_interest=int(data.get("openInterest", 0)),
            bid_price=float(data.get("bidPrice", 0.0)),
            ask_price=float(data.get("askPrice", 0.0))
        )

@dataclass
class OptionChain:
    """
    Represents an option chain.
    """
    expiry_date: datetime.datetime
    spot_price: float
    contracts: Dict[int, Dict[str, OptionContract]]  # Strike -> OptionType -> Contract
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any], expiry_date: datetime.datetime) -> 'OptionChain':
        """
        Create an OptionChain object from API response.
        
        Args:
            data: Option chain data from API
            expiry_date: Expiry date
            
        Returns:
            OptionChain object
        """
        spot_price = float(data.get("spotPrice", 0.0))
        contracts = {}
        
        # Process strike prices
        for strike_str, strike_data in data.get("strikePrices", {}).items():
            strike = int(strike_str)
            contracts[strike] = {}
            
            # Process CE contract
            if "CE" in strike_data:
                contracts[strike]["CE"] = OptionContract.from_api_response(
                    strike_data["CE"], expiry_date
                )
                
            # Process PE contract
            if "PE" in strike_data:
                contracts[strike]["PE"] = OptionContract.from_api_response(
                    strike_data["PE"], expiry_date
                )
                
        return cls(
            expiry_date=expiry_date,
            spot_price=spot_price,
            contracts=contracts
        )
