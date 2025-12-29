# BingX API Signature Fix - December 29, 2025 (Updated)

## Issue Fixed

**Problem**: Signature verification failed with error:
```
Signature verification failed due to signature mismatch,please verify our authentication signature and try to run our sample code from the link "https://bingx-api.github.io/docs/#/en-us/spot/account-api.html#Query%20Assets"
```

This error occurred specifically when executing VIP trades during the leverage setting step.

**Root Cause Analysis**:
1. **POST request body issue**: The original code was sending parameters BOTH in the query string AND as a JSON body for POST requests
2. **Double parameter sending**: BingX API expects parameters in the query string ONLY for signed requests
3. **JSON body conflict**: Sending a JSON body alongside signed query parameters caused signature mismatch

## Solution Implemented

### 1. Fixed Request Handling (`src/bingx_client.py`)

**Before (Incorrect)**:
```python
# Parameters sent in BOTH query string AND JSON body - WRONG!
if method.upper() == 'POST' and body_params and signed:
    query = self._sign_request(body_params)
    url = f"{url}?{query}"
# ...
if method.upper() == 'POST' and body_params:
    request_kwargs['json'] = body_params  # This caused the signature mismatch!
```

**After (Correct)**:
```python
# For signed requests, ALL parameters go in query string ONLY - no JSON body
if signed:
    all_params = {**params, **body_params}
    query = self._sign_request(all_params)
    url = f"{url}?{query}"
# NOTE: For BingX signed requests, do NOT send JSON body
# All parameters are in the query string
```

### 2. Fixed Signature Generation

The signature generation now follows BingX USDT-M Swap V2 API specification:

```python
def _sign_request(self, params: Dict[str, Any]) -> str:
    """
    CRITICAL: Per BingX USDT-M Swap V2 API documentation:
    1. Assemble parameters as: key1=value1&key2=value2&timestamp=xxx
    2. Parameters MUST be sorted alphabetically by key
    3. Sign the raw query string (NOT URL encoded) with HMAC SHA256
    4. Append signature to the query string
    """
    # Create a copy to avoid modifying the original
    sign_params = dict(params)
    
    # Add timestamp (milliseconds)
    sign_params['timestamp'] = int(time.time() * 1000)
    
    # Sort parameters alphabetically by key
    sorted_params = sorted(sign_params.items())
    
    # Build query string (raw values, not URL encoded)
    param_pairs = []
    for key, value in sorted_params:
        if value is None:
            continue
        if isinstance(value, str) and value == '':
            continue
        param_pairs.append(f"{key}={value}")
    
    query_string = "&".join(param_pairs)
    
    # Create HMAC SHA256 signature
    signature = hmac.new(
        self.api_secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    # Return query string with signature appended
    return f"{query_string}&signature={signature}"
```

### 3. Enhanced Connection Testing

Added comprehensive connection testing that verifies BOTH public and signed endpoints:

```python
async def test_connection(self) -> Tuple[bool, str]:
    """
    Tests both unsigned (public) and signed (private) endpoints.
    """
    # Step 1: Test public endpoint (contracts list)
    response = await self._request('GET', '/openApi/swap/v2/quote/contracts', signed=False)
    
    # Step 2: Test signed endpoint (balance) to verify credentials
    response = await self._request('GET', '/openApi/swap/v2/user/balance', signed=True)
```

## Files Modified

### 1. `src/bingx_client.py`
- Fixed `_sign_request()` method - proper parameter handling and signature generation
- Fixed `_request()` method - removed JSON body for signed requests
- Enhanced `test_connection()` - now tests both public AND signed endpoints
- Added better debug logging

### 2. `tests/test_image_analyzer.py`
- Updated test expectations to use `BASE-USDT` format (BingX Swap V2 requirement)

## API Compliance (BingX USDT-M Swap V2)

The fix ensures compliance with:
- https://bingx-api.github.io/docs/#/en-us/swapV2/introduce
- https://bingx-api.github.io/docs/#/en-us/swapV2/market-api.html

Key requirements now met:
1. ✅ Symbol format: `BASE-USDT` (with dash)
2. ✅ Parameters in query string only (no JSON body for signed requests)
3. ✅ HMAC SHA256 signature on raw query string
4. ✅ Timestamp in milliseconds
5. ✅ Parameters sorted alphabetically
6. ✅ API key in `X-BX-APIKEY` header

## Expected Results

With these fixes:

✅ **Signature verification should pass** - Correct request format for BingX Swap V2 API  
✅ **Leverage setting will work** - No more signature mismatch on leverage endpoint  
✅ **Order placement will work** - Proper parameter handling for all signed endpoints  
✅ **Early failure detection** - Connection test verifies credentials before trading  
✅ **Better debugging** - Detailed logs for troubleshooting  

## Troubleshooting Steps

If signature verification still fails:

1. **Run with debug logging** - Set log level to DEBUG to see signature details
2. **Verify API credentials** - Ensure `BINGX_API_KEY` and `BINGX_API_SECRET` are correct
3. **Check API permissions** - API key needs Perpetual Futures trading permissions
4. **IP Whitelist** - If enabled in BingX dashboard, add your server IP
5. **Clock synchronization** - Ensure server time is accurate (within 5000ms of BingX server)

## Testing

All 125 tests pass:
```
============================= 125 passed in 1.01s ==============================
```

The signature generation has been verified against the official BingX API documentation examples.
