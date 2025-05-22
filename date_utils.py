"""
Utility functions for date operations in the trading application.
"""

import datetime
import logging
from typing import Optional, List

# Configure logger
logger = logging.getLogger(__name__)

def get_expiry_date_n_weeks_ahead(weeks: int) -> Optional[datetime.date]:
    """
    Get expiry date N weeks ahead.
    
    Args:
        weeks: Number of weeks ahead
        
    Returns:
        Expiry date or None if calculation fails
    """
    logger.debug(f"Calculating expiry date {weeks} weeks ahead")
    try:
        today = datetime.date.today()
        target_date = today + datetime.timedelta(weeks=weeks)
        
        # Find the Thursday of that week (weekday 3)
        days_to_add = (3 - target_date.weekday()) % 7
        expiry_date = target_date + datetime.timedelta(days=days_to_add)
        
        logger.debug(f"Calculated expiry date: {expiry_date}")
        return expiry_date
    except Exception as e:
        logger.error(f"Error calculating expiry date: {str(e)}", exc_info=True)
        return None

def is_trading_day(date: datetime.date, holidays: List[str]) -> bool:
    """
    Check if a date is a trading day.
    
    Args:
        date: Date to check
        holidays: List of holidays in YYYY-MM-DD format
        
    Returns:
        True if trading day, False otherwise
    """
    logger.debug(f"Checking if {date} is a trading day")
    
    # Check if weekend
    if date.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
        logger.debug(f"{date} is a weekend (weekday {date.weekday()})")
        return False
        
    # Check if holiday
    date_str = date.strftime("%Y-%m-%d")
    if date_str in holidays:
        logger.debug(f"{date} is a holiday")
        return False
        
    logger.debug(f"{date} is a trading day")
    return True

def get_next_trading_day(date: datetime.date, holidays: List[str]) -> datetime.date:
    """
    Get the next trading day after a given date.
    
    Args:
        date: Starting date
        holidays: List of holidays in YYYY-MM-DD format
        
    Returns:
        Next trading day
    """
    logger.debug(f"Finding next trading day after {date}")
    next_day = date + datetime.timedelta(days=1)
    
    while not is_trading_day(next_day, holidays):
        logger.debug(f"{next_day} is not a trading day, checking next day")
        next_day += datetime.timedelta(days=1)
        
    logger.debug(f"Next trading day after {date} is {next_day}")
    return next_day

def is_trading_time(current_time: datetime.time, start_time: datetime.time, end_time: datetime.time) -> bool:
    """
    Check if current time is within trading hours.
    
    Args:
        current_time: Current time
        start_time: Trading start time
        end_time: Trading end time
        
    Returns:
        True if within trading hours, False otherwise
    """
    logger.debug(f"Checking if {current_time} is within trading hours ({start_time} - {end_time})")
    is_trading = start_time <= current_time <= end_time
    logger.debug(f"Is trading time: {is_trading}")
    return is_trading
