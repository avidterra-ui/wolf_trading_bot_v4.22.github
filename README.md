# 🐺 Wolf Trading Bot v4.2

**Telegram → BingX Auto-Trading System**

A production-ready Python bot that monitors THE WOLF (CRYPTO)® Telegram channel for trading signals and automatically executes trades on BingX Futures.

---

## 📋 Features

### Signal Detection
- ✅ **VIP Signals**: Automatically detects forwarded signals from WOLF OFFICIAL VIP
  - **Direction extracted from IMAGE via OCR** (Bitunix card shows Long/Short badge)
  - Caption contains symbol only
- ✅ **FREE Signals**: Parses direct text signals with full trade details
  - **ALL data extracted from CAPTION TEXT via Regex**
  - Images only supplement TP/SL if not in text
- ✅ **Image TP/SL Extraction**: Reads TP/SL values from attached chart images
- ✅ **First-Post Detection**: Only trades the FIRST VIP signal (ignores replies/updates)
- ✅ **Results Filtering**: Automatically ignores promotional and results posts

### Trading Execution
- ✅ **BingX Futures**: Places **LIMIT ORDERS ONLY** with TP/SL
- ✅ **NO MARKET ORDERS**: Strict limit-order policy to minimize fees/slippage
- ✅ **Leverage Management**: Configurable up to 50× (or max available)
- ✅ **Position Sizing**: Fixed USDT amount per trade ($1 default)
- ✅ **Max Trades Per Day**: User-defined daily trade limit to protect capital
- ✅ **Multi-Signal Mode**: Configurable max trades per symbol/direction per day
- ✅ **Bi-Directional Trading**: Support LONG then SHORT on same pair (scalping mode)

### Safety & Security
- ✅ **Dry Run Mode**: Test without real trades
- ✅ **Price Tolerance**: Skip trades if price deviates too much (1-5%)
- ✅ **SL Hard Cap**: Maximum 5% stop loss (without leverage)
- ✅ **Minimal Permissions**: Trading-only API access
- ✅ **Unfilled Order Policy**: CANCEL only (never convert to market)

### User Experience
- ✅ **Interactive Startup**: Configure settings on every launch
- ✅ **Colored Console**: Rich formatted output
- ✅ **Real-time Feedback**: See what the bot is processing

---

## 🆕 What's New in v4.2

### 1. BingX USDT-M Swap V2 API Compliance (CRITICAL)
- **Symbol Format**: All symbols now use `BASE-USDT` format (with dash)
  - ✅ VALID: `BTC-USDT`, `ETH-USDT`, `TRADOOR-USDT`
  - ❌ INVALID: `BTCUSDT`, `BTC/USDT`
- **Mandatory Symbol Validation**: Before ANY trade:
  - Calls `GET /openApi/swap/v2/quote/contracts`
  - Verifies `status == 1` and `apiStateOpen == "true"`
  - If validation fails → trade skipped safely
- **Leverage API Fixed**: Proper parameter types
  - `leverage` MUST be integer (not string)
  - `side` MUST be `"LONG"` or `"SHORT"` (not `"BUY"`/`"SELL"`)
  - If leverage fails → DO NOT place order

### 2. Signal Source Identification
- **VIP Signals**: Direction MUST be extracted from IMAGE via OCR
  - Caption only contains symbol (e.g., #BTC), NOT direction
  - OCR reads "Long" or "Short" badge from Bitunix trading card
- **FREE Signals**: ALL data extracted from CAPTION via Regex
  - Do NOT ignore signals just because they have images
  - Image TP/SL supplements text if needed

### 3. TP/SL Strategy by Signal Type
- **VIP Signals**: Always use MANUAL percentages (no TP/SL in images)
- **FREE Signals**: Choose between:
  - `from_signal`: Parse TP/SL from text/image
  - `manual`: Use configured percentages

### 4. Max Trades Per Day
- New daily trade limit to protect capital
- Default: 5 trades per day
- Set to 0 for unlimited (not recommended)

### 5. Strict No Market Orders
- **ONLY LIMIT ORDERS** are permitted
- Unfilled orders are CANCELLED after timeout
- Never converted to market orders
- Minimizes trading fees and slippage

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**: Download from [python.org](https://python.org)
2. **Tesseract OCR**: Download from [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
   - Add to PATH: `C:\Program Files\Tesseract-OCR`
3. **Telegram API**: Get credentials from [my.telegram.org](https://my.telegram.org)
4. **BingX API**: Create API key with **TRADING ONLY** permissions

### Installation

```batch
# 1. Run the installer
install.bat

# 2. Edit .env with your API keys
notepad .env

# 3. Authenticate with Telegram
auth.bat

# 4. Start the bot
run_bot.bat
```

### Manual Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup configuration
copy config\config.example.yaml config\config.yaml
copy .env.example .env

# Edit .env with your API keys
# Then run:
python -m src.main
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```bash
# Telegram (from https://my.telegram.org)
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=abcdef1234567890

# BingX (TRADING ONLY permissions!)
BINGX_API_KEY=your_api_key
BINGX_API_SECRET=your_api_secret
```

### Interactive Startup Options

On every startup, you'll configure:

| Setting | Description | Default |
|---------|-------------|---------|
| VIP Signals | Enable forwarded VIP signals | Yes |
| FREE Signals | Enable direct text signals | Yes |
| Position Size | USDT per trade | $1.00 |
| Leverage | Trading leverage | 50× |
| **Max Trades Per Day** | Daily trade limit (NEW) | 5 |
| **VIP TP/SL Mode** | Always manual | N/A |
| **FREE TP/SL Mode** | from_signal or manual | from_signal |
| Take Profit | % without leverage | 10% |
| Stop Loss | % without leverage (max 5%) | 2% |
| Price Tolerance | Max deviation from entry | 3% |
| Opposite Direction | Allow LONG & SHORT same pair | Yes |
| Max Same Direction | Trades per symbol/direction/day | 1 |
| Dry Run | Test without real trades | Yes |

---

## 📊 Signal Types

### VIP Signal (Forwarded)
```
THE WOLF (CRYPTO)®
Forwarded from 🐺 WOLF OFFICIAL VIP
─────────────────────────────────
[Bitunix Pro Screenshot with "Long" badge]
#BTC

Caption: Symbol ONLY (no direction!)
Direction: Extracted from IMAGE via OCR
─────────────────────────────────
```

### FREE Signal (Direct - Text)
```
👍THE WOLF SCALPER👍

✔️COIN NAME: 1000LUNC(USDT)
LEVERAGE: 75x
🔼TRADE TYPE: LONG 📈
✔️ENTRY PRICE (0.04040-0.03950)

☄️TAKE-PROFITS
1️⃣ 0.04150
2️⃣ 0.04250
3️⃣ 0.04400

STOP LOSS: 0.03860

Caption: ALL data (Symbol, Direction, Entry, TP, SL)
Extracted via: Regex parsing
```

### FREE Signal (With Chart Image)
```
[Attached TradingView Chart Image with overlay:]
┌─────────────────────────────────────────┐
│ 🪙 COIN NAME: POWER(USDT)               │
│ ✅ LEVERAGE: 75x                         │
│ 📈 TRADE TYPE: LONG                      │
│ 📉 ENTRY PRICE (0.3280-0.3200)           │
│ 1️⃣ 0.3350                               │
│ 2️⃣ 0.3400                               │
│ 3️⃣ 0.3460                               │
│ 🤖 STOP LOSS: 0.3100                    │
└─────────────────────────────────────────┘

Caption: Primary source for ALL data
Image: Only supplements TP/SL if not in text
```

---

## 📈 TP/SL System

### Leverage Awareness

All percentages are displayed **WITH and WITHOUT** leverage:

| Without Leverage | With 50× Leverage |
|------------------|-------------------|
| 1% | 50% |
| 2% (default SL) | 100% |
| 5% (max SL - HARD CAP) | 250% |
| 10% (default TP) | 500% |

### TP/SL Modes by Signal Type (v4.1)

| Signal Type | Mode Options | Reason |
|-------------|--------------|--------|
| **VIP** | MANUAL only | VIP images don't contain TP/SL |
| **FREE** | from_signal OR manual | User choice at startup |

### SL Hard Cap

Regardless of signal source or mode, Stop Loss is **HARD CAPPED at 5%** (without leverage).
- At 50× leverage: Maximum 250% SL
- If signal SL > 5%, bot adjusts to 5%

---

## 🔒 Security

### Telegram Permissions
- ✅ Read messages from THE WOLF (CRYPTO)® only
- ❌ Cannot read private messages
- ❌ Cannot read other channels
- ❌ Cannot send messages

### BingX Permissions
- ✅ Place futures trades (LIMIT ORDERS ONLY)
- ✅ Set leverage
- ✅ Check balance
- ❌ **Cannot use MARKET orders** (strict policy)
- ❌ Cannot withdraw
- ❌ Cannot access wallet

### Recommendations
1. Create BingX API key with **TRADING ONLY** permissions
2. Enable **IP whitelist** in BingX
3. Never share your `.env` file
4. Start with **DRY RUN** mode

---

## 📁 Project Structure

```
wolf-trading-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── startup.py              # Interactive configuration
│   ├── telegram_client.py      # Telegram monitoring
│   ├── message_classifier.py   # Message type detection
│   ├── free_signal_parser.py   # FREE signal Regex parsing
│   ├── image_analyzer.py       # OCR for VIP & FREE images
│   ├── tolerance_checker.py    # Price tolerance
│   ├── tp_sl_calculator.py     # TP/SL calculations (v4.1)
│   ├── bingx_client.py         # BingX API (LIMIT ONLY)
│   ├── trade_executor.py       # Order management (v4.1)
│   ├── feedback.py             # Console output
│   ├── models.py               # Data classes (v4.1)
│   └── utils/
│       ├── logging_setup.py
│       └── security.py
├── tests/
│   ├── test_message_classifier.py
│   ├── test_free_signal_parser.py
│   ├── test_tolerance.py
│   ├── test_tp_sl.py
│   ├── test_trade_executor.py
│   └── test_image_analyzer.py
├── config/
│   ├── config.yaml
│   └── config.example.yaml
├── logs/
├── .env.example
├── requirements.txt
├── install.bat
├── auth.bat
├── run_bot.bat
└── README.md
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_free_signal_parser.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## ⚠️ Risk Disclaimer

**Trading cryptocurrencies involves substantial risk of loss.** This bot is provided as-is with no guarantees. You are solely responsible for your trading decisions.

- Always start with **DRY RUN** mode
- Use small position sizes ($1 recommended for $50 capital)
- Monitor the bot regularly
- Never risk money you can't afford to lose

---

## 📝 License

MIT License - See LICENSE file for details.

---

## 🆘 Troubleshooting

### Telegram Authentication Failed
- Ensure your `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are correct
- Run `auth.bat` to create a new session

### OCR Not Working
- Verify Tesseract is installed and in PATH
- Try uncommenting `tesseract_cmd` in config.yaml
- VIP signals require OCR for direction detection

### Orders Not Filling
- Increase price tolerance
- Check if symbol exists on BingX
- Verify sufficient balance
- Note: Orders are CANCELLED after timeout (never market)

### Bot Missing Signals
- Check if signal type is enabled
- Verify channel username is correct
- Check logs in `logs/` folder

### Daily Limit Reached
- Increase `max_trades_per_day` setting
- Or wait until next day
- Trade limit resets at midnight (local time)

### Image TP/SL Not Extracted
- Ensure Tesseract OCR is installed
- Check image quality (blurry images may fail)
- The bot will fall back to manual values if image fails

---

## 📜 Changelog

### v4.2 (Current)
- ✅ **BingX USDT-M Swap V2 Compliance**: Full API compatibility
- ✅ **Symbol Format**: BASE-USDT with dash (e.g., `BTC-USDT`)
- ✅ **Mandatory Symbol Validation**: Via contracts endpoint before trading
- ✅ **Fixed Leverage API**: Integer leverage, LONG/SHORT side parameters
- ✅ **Zero "symbol not found" errors**: Proper format and validation
- ✅ **Zero "invalid parameters" errors**: Correct API parameter types

### v4.1
- ✅ **Signal Source Identification**: VIP=OCR, FREE=Regex (CRITICAL)
- ✅ **Separate TP/SL Modes**: VIP always manual, FREE configurable
- ✅ **Max Trades Per Day**: Daily trade limit setting
- ✅ **Strict No Market Orders**: LIMIT only, cancel if unfilled
- ✅ **SL Hard Cap**: 5% without leverage enforced

### v4.0
- Initial production release
- VIP and FREE signal detection
- BingX futures trading
- Interactive startup configuration

---

## 📊 Acceptance Criteria (v4.2)

| ID | Requirement | Status |
|----|-------------|--------|
| F1 | VIP signals use OCR for direction | ✅ |
| F2 | FREE signals use Regex for caption | ✅ |
| F3 | Max Trades Per Day setting | ✅ |
| F4 | LIMIT ORDERS ONLY (no market) | ✅ |
| F5 | VIP=manual, FREE=from_signal/manual TP/SL | ✅ |
| F6 | Interactive startup menu | ✅ |
| F7 | Symbol format BASE-USDT (with dash) | ✅ |
| F8 | Mandatory symbol validation via contracts API | ✅ |
| F9 | Leverage API with integer + LONG/SHORT | ✅ |
| F10 | Zero "symbol not found" errors | ✅ |
| F11 | Zero "invalid parameters" errors | ✅ |

---

**Made with 🐺 by Wolf Trading Bot**
