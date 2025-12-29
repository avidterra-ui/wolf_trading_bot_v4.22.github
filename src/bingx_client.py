"""
Secure BingX API client for Wolf Trading Bot v4.1.
Implements trading-only operations with minimal permissions.

CRITICAL v4.1 REQUIREMENT:
- ONLY LIMIT ORDERS are permitted
- NO MARKET ORDERS under any circumstances
- Unfilled limit orders are CANCELLED, never converted to market
"""

import time
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlencode
import aiohttp

from .models import TradeDirection, OrderStatus
from .utils.logging_setup import get_logger
from . import feedback

logger = get_logger(__name__)


class BingXError(Exception):
    """Base exception for BingX API errors."""
    pass


class InsufficientBalanceError(BingXError):
    """Not enough balance to place trade."""
    pass


class SymbolNotFoundError(BingXError):
    """Symbol not available on exchange or not tradeable."""


class SymbolValidationError(BingXError):
    """Symbol validation failed - not found in contracts list or not tradeable."""


class LeverageSetError(BingXError):
    """Failed to set leverage - must succeed before placing order."""
    pass


class OrderFailedError(BingXError):
    """Order placement failed."""
    pass


class SecureBingXClient:
    """
    Secure BingX API client with minimal permissions.
    
    Security measures:
    1. Only uses TRADING endpoints (not withdrawal)
    2. API key should have trading-only permissions
    3. Does NOT access account personal data
    4. All requests signed with HMAC-SHA256
    
    CRITICAL v4.1 TRADING POLICY:
    - ONLY LIMIT ORDERS are used (NO MARKET ORDERS)
    - Unfilled orders are cancelled, never converted to market
    - This minimizes fees and slippage
    """
    
    # STRICT: Order type is LIMIT only
    ORDER_TYPE = "LIMIT"
    
    # Permitted endpoints (trading operations only)
    PERMITTED_ENDPOINTS = [
        "/openApi/swap/v2/trade/order",      # Place order
        "/openApi/swap/v2/trade/leverage",   # Set leverage
        "/openApi/swap/v2/trade/allOrders",  # Query orders
        "/openApi/swap/v2/quote/price",      # Get price
        "/openApi/swap/v2/quote/contracts",  # Get contract info
        "/openApi/swap/v2/user/balance",     # Available balance
        "/openApi/swap/v1/trade/fullOrder",  # Full order (TP/SL)
    ]
    
    BASE_URL = "https://open-api.bingx.com"
    
    def __init__(self, api_key: str, api_secret: str):
        """
        Initialize BingX client.
        
        Args:
            api_key: BingX API key (trading permissions only)
            api_secret: BingX API secret
        """
        # Validate API credentials
        if not api_key or not api_secret:
            raise ValueError("API key and secret are required")
        
        # Clean and validate API key format
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        
        # Log warnings for common issues (without exposing secrets)
        if len(self.api_key) < 10:
            logger.warning("API key seems too short, please verify it's correct")
        if len(self.api_secret) < 10:
            logger.warning("API secret seems too short, please verify it's correct")
        
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cache for contract info
        self._contracts: Dict[str, Dict] = {}
        self._contracts_initialized = False
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _sign_request(self, params: Dict[str, Any]) -> str:
        """
        Sign request parameters with HMAC-SHA256 according to BingX API specification.
        
        CRITICAL: Per BingX USDT-M Swap V2 API documentation:
        1. Assemble parameters as: key1=value1&key2=value2&timestamp=xxx
        2. Parameters MUST be sorted alphabetically by key
        3. Sign the raw query string (NOT URL encoded) with HMAC SHA256
        4. Append signature to the query string
        
        NOTE: This method does NOT modify the input params dict.
        
        Returns:
            Query string with signature appended (ready for URL)
        """
        # Create a copy to avoid modifying the original
        sign_params = dict(params)
        
        # Add timestamp (milliseconds)
        sign_params['timestamp'] = int(time.time() * 1000)
        
        # Sort parameters alphabetically by key and filter out falsy values
        # (matching bingx-py library behavior)
        sorted_params = sorted(sign_params.items())
        
        # Build query string for signature calculation
        # Format: key1=value1&key2=value2&...
        # IMPORTANT: 
        # - Values are NOT URL encoded for signature calculation
        # - Falsy values (None, empty string, 0) should be skipped per bingx-py
        # - BUT numeric 0 should be kept if explicitly set
        param_pairs = []
        for key, value in sorted_params:
            # Skip None values, but keep 0 and False as they might be intentional
            if value is None:
                continue
            # Skip empty strings
            if isinstance(value, str) and value == '':
                continue
            # Convert value to string
            param_pairs.append(f"{key}={value}")
        
        query_string = "&".join(param_pairs)
        
        # Debug logging for signature troubleshooting
        logger.debug(f"Signature query string: {query_string}")
        
        # Create HMAC SHA256 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        logger.debug(f"Generated signature: {signature[:16]}...")  # Only log first 16 chars for security
        
        # Build final query string with signature appended
        final_query = f"{query_string}&signature={signature}"
        
        return final_query
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        signed: bool = True,
        body_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make API request following BingX USDT-M Swap V2 API specification.
        
        CRITICAL: Per BingX API documentation:
        - All signed requests send parameters via QUERY STRING (not JSON body)
        - Signature is computed from query string and appended to it
        - API key is passed in X-BX-APIKEY header
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint
            params: Request parameters (for query string)
            signed: Whether to sign the request
            body_params: Parameters to send (will be merged into query string for signed requests)
            
        Returns:
            API response as dictionary
        """
        session = await self._get_session()
        params = params or {}
        body_params = body_params or {}
        
        headers = {
            'X-BX-APIKEY': self.api_key,
        }
        
        url = f"{self.BASE_URL}{endpoint}"
        
        # Build query string based on request type
        if signed:
            # For signed requests, ALL parameters go in query string with signature
            # Merge params and body_params for signing
            all_params = {**params, **body_params}
            query = self._sign_request(all_params)
            url = f"{url}?{query}"
            logger.debug(f"Signed request URL: {url}")
        elif params or body_params:
            # For unsigned requests, just urlencode params
            all_params = {**params, **body_params}
            url = f"{url}?{urlencode(all_params)}"
        
        try:
            request_kwargs = {
                'method': method,
                'url': url,
                'headers': headers
            }
            
            # NOTE: For BingX signed requests, do NOT send JSON body
            # All parameters are in the query string
            
            async with session.request(**request_kwargs) as response:
                data = await response.json()
                
                if response.status != 200:
                    logger.error(f"API error: {response.status} - {data}")
                    raise BingXError(f"API error: {data.get('msg', 'Unknown error')}")
                
                if data.get('code') != 0:
                    error_msg = data.get('msg', 'Unknown error')
                    logger.error(f"BingX error: {error_msg}")
                    
                    if 'insufficient' in error_msg.lower() or 'balance' in error_msg.lower():
                        raise InsufficientBalanceError(error_msg)
                    if 'symbol' in error_msg.lower() and 'not' in error_msg.lower():
                        raise SymbolNotFoundError(error_msg)
                    
                    raise BingXError(error_msg)
                
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"Network error: {e}")
            raise BingXError(f"Network error: {e}")
    
    async def test_connection(self) -> Tuple[bool, str]:
        """
        Test API connection and credentials.
        
        Tests both unsigned (public) and signed (private) endpoints.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Step 1: Test unsigned endpoint (contracts list)
            logger.info("Testing public API connection...")
            response = await self._request(
                'GET',
                '/openApi/swap/v2/quote/contracts',
                signed=False
            )
            
            if response.get('code') != 0:
                return False, f"Public API error: {response.get('msg', 'Unknown error')}"
            
            logger.info("Public API connection successful")
            
            # Step 2: Test signed endpoint (balance) to verify API credentials
            logger.info("Testing signed API connection (verifying credentials)...")
            try:
                response = await self._request(
                    'GET',
                    '/openApi/swap/v2/user/balance',
                    signed=True
                )
                
                if response.get('code') != 0:
                    return False, f"Signed API error: {response.get('msg', 'Unknown error')}"
                
                logger.info("Signed API connection successful - credentials verified")
                return True, "API connection and credentials verified successfully"
                
            except BingXError as e:
                error_str = str(e).lower()
                if 'signature' in error_str:
                    return False, f"Signature verification failed - please check your API secret. Error: {e}"
                elif 'api' in error_str and 'key' in error_str:
                    return False, f"API key error - please check your API key. Error: {e}"
                else:
                    return False, f"Signed API failed: {e}"
                
        except Exception as e:
            return False, f"Connection test failed: {e}"
    
    async def initialize_contracts_cache(self) -> bool:
        """
        Initialize the contracts cache from API.
        Should be called during bot startup to ensure symbol validation works.
        
        Returns:
            True if successful, False otherwise
        """
        if self._contracts_initialized:
            return True
            
        success = await self.refresh_contracts_cache()
        if success:
            self._contracts_initialized = True
            logger.info("Contracts cache initialized successfully")
        else:
            logger.error("Failed to initialize contracts cache")
        
        return success
    
    async def refresh_contracts_cache(self) -> bool:
        """
        Refresh the contracts cache from API.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self._request(
                'GET',
                '/openApi/swap/v2/quote/contracts',
                signed=False
            )
            
            contracts = response.get('data', [])
            self._contracts.clear()
            for contract in contracts:
                # Use exact symbol field as key
                self._contracts[contract['symbol']] = contract
            
            logger.info(f"Contracts cache refreshed: {len(self._contracts)} symbols")
            return True
            
        except BingXError as e:
            logger.error(f"Failed to refresh contracts cache: {e}")
            return False
    
    async def get_contract_info(self, symbol: str) -> Optional[Dict]:
        """
        Get contract information for a symbol.
        
        CRITICAL: Symbol MUST be in BingX Swap V2 format with dash: BASE-USDT
        
        Returns:
            Contract info or None if not found
        """
        # Check cache first
        if symbol in self._contracts:
            return self._contracts[symbol]
        
        # Refresh cache if symbol not found
        await self.refresh_contracts_cache()
        
        return self._contracts.get(symbol)
    
    async def validate_symbol(self, symbol: str) -> Tuple[bool, Optional[Dict], str]:
        """
        MANDATORY validation of symbol before ANY trade.
        
        CRITICAL: This MUST be called before placing any order.
        Per BingX USDT-M Swap V2 API:
        - Symbol MUST match exactly (e.g., TRADOOR-USDT)
        - status MUST == 1
        - apiStateOpen MUST == "true" (or truthy)
        
        Args:
            symbol: Trading symbol in BASE-USDT format
            
        Returns:
            Tuple of (is_valid, contract_info, error_message)
        """
        logger.info(f"Validating symbol: {symbol}")
        
        # Ensure contracts cache is initialized
        if not self._contracts_initialized:
            logger.info("Initializing contracts cache for symbol validation...")
            init_success = await self.initialize_contracts_cache()
            if not init_success:
                error_msg = f"Failed to initialize contracts cache. Cannot validate symbol '{symbol}'. Trade skipped safely."
                logger.error(error_msg)
                return False, None, error_msg
        
        contract = self._contracts.get(symbol)
        
        if not contract:
            error_msg = f"Symbol '{symbol}' NOT FOUND in BingX contracts list. Trade skipped safely."
            logger.error(error_msg)
            return False, None, error_msg
        
        # Check status == 1 (active)
        status = contract.get('status')
        if status != 1:
            error_msg = f"Symbol '{symbol}' has status={status}, expected 1. Trade skipped safely."
            logger.error(error_msg)
            return False, contract, error_msg
        
        # Check apiStateOpen == "true" (API trading enabled)
        api_state = contract.get('apiStateOpen')
        # Handle both string "true" and boolean True
        if str(api_state).lower() != 'true':
            error_msg = f"Symbol '{symbol}' has apiStateOpen={api_state}, expected 'true'. Trade skipped safely."
            logger.error(error_msg)
            return False, contract, error_msg
        
        logger.info(f"Symbol '{symbol}' validated successfully: status={status}, apiStateOpen={api_state}")
        return True, contract, ""
    
    async def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current market price for a symbol.
        """
        try:
            response = await self._request(
                'GET',
                '/openApi/swap/v2/quote/price',
                params={'symbol': symbol},
                signed=False
            )
            
            data = response.get('data', {})
            if data:
                return float(data.get('price', 0))
            return None
            
        except BingXError as e:
            logger.error(f"Failed to get price for {symbol}: {e}")
            return None
    
    async def get_available_balance(self) -> float:
        """
        Get available USDT balance for trading.
        """
        try:
            response = await self._request(
                'GET',
                '/openApi/swap/v2/user/balance',
                signed=True
            )
            
            balance_data = response.get('data', {}).get('balance', {})
            available = float(balance_data.get('availableMargin', 0))
            logger.debug(f"Available balance: {available} USDT")
            return available
            
        except BingXError as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0
    
    async def set_leverage(self, symbol: str, leverage: int, direction: str = "LONG") -> int:
        """
        Set leverage for a symbol. MUST succeed before placing any order.
        
        CRITICAL BingX Swap V2 API Requirements:
        - symbol: MUST match contracts list exactly (e.g., "TRADOOR-USDT")
        - leverage: MUST be an INTEGER (not string "75")
        - side: MUST be "LONG" or "SHORT" (not "BUY"/"SELL")
        
        Args:
            symbol: Trading symbol in BASE-USDT format
            leverage: Desired leverage (INTEGER)
            direction: "LONG" or "SHORT" (sets leverage for this side)
            
        Returns:
            Actual leverage set (may be capped at max)
            
        Raises:
            LeverageSetError: If leverage setting fails - DO NOT proceed with order
        """
        # CRITICAL: Ensure leverage is integer, not string
        leverage = int(leverage)
        
        # Validate direction parameter
        if direction not in ("LONG", "SHORT"):
            raise LeverageSetError(f"Invalid side '{direction}'. Must be 'LONG' or 'SHORT'.")
        
        # Get max leverage for symbol
        contract = await self.get_contract_info(symbol)
        if contract:
            max_leverage = int(contract.get('maxLongLeverage', 125))
            if leverage > max_leverage:
                logger.warning(f"{symbol}: Requested {leverage}x, max is {max_leverage}x")
                feedback.log_leverage_fallback(symbol, leverage, max_leverage)
                leverage = max_leverage
        
        try:
            # Set leverage for the specified side only
            logger.info(f"Setting {direction} leverage for {symbol}: {leverage}x")
            await self._request(
                'POST',
                '/openApi/swap/v2/trade/leverage',
                body_params={
                    'symbol': symbol,         # MUST match contracts exactly
                    'leverage': leverage,     # MUST be integer
                    'side': direction,       # MUST be "LONG" or "SHORT"
                },
                signed=True
            )
            
            feedback.log_leverage_set(symbol, leverage)
            logger.info(f"Leverage set successfully for {symbol}: {leverage}x ({direction} side)")
            return leverage
            
        except BingXError as e:
            error_msg = f"CRITICAL: Failed to set leverage for {symbol}: {e}. Trade will NOT proceed."
            logger.error(error_msg)
            raise LeverageSetError(error_msg)
    
    async def place_limit_order(
        self,
        symbol: str,
        direction: TradeDirection,
        quantity: float,
        price: float,
        tp_price: Optional[float] = None,
        sl_price: Optional[float] = None,
    ) -> Optional[str]:
        """
        Place a LIMIT order with optional TP/SL.
        
        CRITICAL v4.1: Only LIMIT orders are permitted.
        NO MARKET ORDERS under any circumstances.
        
        Args:
            symbol: Trading symbol
            direction: LONG or SHORT
            quantity: Order quantity
            price: Limit price
            tp_price: Take profit price
            sl_price: Stop loss price
            
        Returns:
            Order ID if successful
        """
        side = "BUY" if direction == TradeDirection.LONG else "SELL"
        position_side = "LONG" if direction == TradeDirection.LONG else "SHORT"
        
        # STRICT: Always use LIMIT order type - NEVER market
        feedback.log_order_placed(self.ORDER_TYPE, symbol, side, price, quantity)
        
        params = {
            'symbol': symbol,
            'side': side,
            'positionSide': position_side,
            'type': self.ORDER_TYPE,  # STRICT: LIMIT only
            'quantity': quantity,
            'price': price,
        }
        
        # Add TP/SL if provided
        if tp_price is not None:
            params['takeProfit'] = json.dumps({
                'type': 'TAKE_PROFIT_MARKET',
                'stopPrice': tp_price,
                'price': tp_price,
                'workingType': 'MARK_PRICE',
            })
        
        if sl_price is not None:
            params['stopLoss'] = json.dumps({
                'type': 'STOP_MARKET',
                'stopPrice': sl_price,
                'price': sl_price,
                'workingType': 'MARK_PRICE',
            })
        
        try:
            response = await self._request(
                'POST',
                '/openApi/swap/v2/trade/order',
                body_params=params,
                signed=True
            )
            
            order_data = response.get('data', {}).get('order', {})
            order_id = order_data.get('orderId')
            
            if order_id:
                logger.info(f"Order placed: {order_id}")
                return str(order_id)
            
            return None
            
        except BingXError as e:
            logger.error(f"Order failed: {e}")
            raise OrderFailedError(str(e))
    
    async def get_order_status(self, symbol: str, order_id: str) -> OrderStatus:
        """
        Get order status.
        """
        try:
            response = await self._request(
                'GET',
                '/openApi/swap/v2/trade/order',
                params={
                    'symbol': symbol,
                    'orderId': order_id,
                },
                signed=True
            )
            
            order_data = response.get('data', {}).get('order', {})
            status = order_data.get('status', '').upper()
            
            status_map = {
                'NEW': OrderStatus.PENDING,
                'PENDING': OrderStatus.PENDING,
                'PARTIALLY_FILLED': OrderStatus.PARTIALLY_FILLED,
                'FILLED': OrderStatus.FILLED,
                'CANCELED': OrderStatus.CANCELLED,
                'CANCELLED': OrderStatus.CANCELLED,
                'FAILED': OrderStatus.FAILED,
            }
            
            return status_map.get(status, OrderStatus.PENDING)
            
        except BingXError as e:
            logger.error(f"Failed to get order status: {e}")
            return OrderStatus.PENDING
    
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        Cancel an order.
        """
        try:
            await self._request(
                'DELETE',
                '/openApi/swap/v2/trade/order',
                params={
                    'symbol': symbol,
                    'orderId': order_id,
                },
                signed=True
            )
            
            feedback.log_order_cancelled(order_id)
            return True
            
        except BingXError as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    async def wait_for_fill(
        self,
        symbol: str,
        order_id: str,
        timeout_seconds: int = 10,
        poll_interval: float = 0.5
    ) -> OrderStatus:
        """
        Wait for order to be filled.
        
        Args:
            symbol: Trading symbol
            order_id: Order ID to wait for
            timeout_seconds: Maximum time to wait
            poll_interval: Seconds between status checks
            
        Returns:
            Final order status
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            status = await self.get_order_status(symbol, order_id)
            
            if status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.FAILED]:
                if status == OrderStatus.FILLED:
                    feedback.log_order_filled(order_id, 0)  # Price would need separate lookup
                return status
            
            await asyncio.sleep(poll_interval)
        
        # Timeout - return current status
        return await self.get_order_status(symbol, order_id)
    
    def calculate_quantity(
        self,
        position_usdt: float,
        price: float,
        contract_info: Optional[Dict] = None
    ) -> float:
        """
        Calculate order quantity from USDT amount.
        
        Args:
            position_usdt: Position size in USDT
            price: Current/entry price
            contract_info: Optional contract info for precision
            
        Returns:
            Quantity adjusted for contract specifications
        """
        quantity = position_usdt / price
        
        # Adjust for contract precision if available
        if contract_info:
            size_precision = contract_info.get('quantityPrecision', 4)
            quantity = round(quantity, size_precision)
            
            # Check minimum quantity
            min_qty = float(contract_info.get('minQty', 0))
            if quantity < min_qty:
                logger.warning(f"Quantity {quantity} below minimum {min_qty}")
                quantity = min_qty
        else:
            quantity = round(quantity, 4)
        
        return quantity
    
    def get_permissions_summary(self) -> str:
        """Return human-readable permissions summary."""
        return """
╔══════════════════════════════════════════════════════════════╗
║                    BINGX API PERMISSIONS                      ║
╠══════════════════════════════════════════════════════════════╣
║ ✅ CAN place futures trades (LIMIT ORDERS ONLY)              ║
║ ✅ CAN set leverage                                          ║
║ ✅ CAN check available balance                               ║
║ ✅ CAN read market prices                                    ║
║ ❌ CANNOT use MARKET orders (strict policy)                  ║
║ ❌ CANNOT withdraw funds                                     ║
║ ❌ CANNOT access wallet                                      ║
║ ❌ CANNOT access personal account data                       ║
║ ❌ CANNOT transfer funds                                     ║
╚══════════════════════════════════════════════════════════════╝

⚠️  TRADING POLICY: Only LIMIT orders - NO MARKET orders
⚠️  RECOMMENDATION: Create API key with TRADING-ONLY permissions
    and enable IP whitelist in BingX dashboard.
        """


# Import asyncio for sleep
import asyncio
