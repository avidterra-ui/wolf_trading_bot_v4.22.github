"""
Price tolerance checker for Wolf Trading Bot.
Validates if current price is within acceptable deviation from entry price.
"""

from typing import Tuple, Optional

from .utils.logging_setup import get_logger
from . import feedback

logger = get_logger(__name__)


def check_price_tolerance(
    current_price: float,
    entry_price: float,
    tolerance_percent: float,
    entry_price_low: Optional[float] = None,
    entry_price_high: Optional[float] = None,
    reference_method: str = "nearest_boundary"
) -> Tuple[bool, float]:
    """
    Check if current price is within tolerance of entry price.
    
    For entry ranges, uses the nearest boundary as reference.
    
    Args:
        current_price: Current market price
        entry_price: Single entry price (if not range)
        tolerance_percent: Maximum allowed deviation (e.g., 0.03 for 3%)
        entry_price_low: Lower bound of entry range
        entry_price_high: Upper bound of entry range
        reference_method: How to calculate reference price
            - "nearest_boundary": Use nearest entry boundary
            - "average": Use average of entry range
            - "entry": Use single entry price
            
    Returns:
        Tuple of (is_within_tolerance, deviation_percent)
    """
    # Determine reference price
    if entry_price_low is not None and entry_price_high is not None:
        # Entry range provided
        if reference_method == "nearest_boundary":
            # Use whichever boundary is closest to current price
            if current_price < entry_price_low:
                reference_price = entry_price_low
            elif current_price > entry_price_high:
                reference_price = entry_price_high
            else:
                # Price is within range - 0% deviation
                feedback.log_tolerance_check(0.0, tolerance_percent, True)
                return True, 0.0
        elif reference_method == "average":
            reference_price = (entry_price_low + entry_price_high) / 2
        else:
            reference_price = entry_price if entry_price else entry_price_high
    else:
        reference_price = entry_price
    
    if reference_price is None or reference_price == 0:
        logger.error("Cannot calculate tolerance: invalid reference price")
        return False, 1.0
    
    # Calculate deviation with floating point precision handling
    deviation = abs(current_price - reference_price) / reference_price
    # Add small epsilon to handle floating point precision in exact matches
    epsilon = 1e-9
    is_within = deviation <= tolerance_percent + epsilon
    
    # Log result
    feedback.log_tolerance_check(deviation, tolerance_percent, is_within)
    
    logger.debug(
        f"Tolerance check: current={current_price}, ref={reference_price}, "
        f"deviation={deviation*100:.2f}%, tolerance={tolerance_percent*100:.1f}%, "
        f"passed={is_within}"
    )
    
    return is_within, deviation


def get_limit_order_price(
    current_price: float,
    direction: str,
    offset_percent: float = 0.001
) -> float:
    """
    Calculate limit order price with small offset for quick fill.
    
    For LONG: slightly above current (willing to pay a bit more)
    For SHORT: slightly below current (willing to sell a bit less)
    
    Args:
        current_price: Current market price
        direction: "LONG" or "SHORT"
        offset_percent: Price offset (default 0.1%)
        
    Returns:
        Limit order price
    """
    offset = current_price * offset_percent
    
    if direction.upper() == "LONG":
        # Pay slightly more for quick fill
        return current_price + offset
    else:
        # Sell slightly less for quick fill
        return current_price - offset


def calculate_price_deviation(
    price1: float,
    price2: float
) -> float:
    """
    Calculate percentage deviation between two prices.
    
    Args:
        price1: First price (reference)
        price2: Second price (to compare)
        
    Returns:
        Deviation as decimal (e.g., 0.03 for 3%)
    """
    if price1 == 0:
        return float('inf')
    return abs(price2 - price1) / price1


def is_price_favorable(
    current_price: float,
    entry_price: float,
    direction: str
) -> Tuple[bool, float]:
    """
    Check if current price is favorable compared to signal entry.
    
    Favorable means:
    - For LONG: current price < entry price (buying cheaper)
    - For SHORT: current price > entry price (selling higher)
    
    Args:
        current_price: Current market price
        entry_price: Signal entry price
        direction: Trade direction
        
    Returns:
        Tuple of (is_favorable, improvement_percent)
    """
    if direction.upper() == "LONG":
        is_favorable = current_price <= entry_price
        improvement = (entry_price - current_price) / entry_price
    else:
        is_favorable = current_price >= entry_price
        improvement = (current_price - entry_price) / entry_price
    
    return is_favorable, improvement
