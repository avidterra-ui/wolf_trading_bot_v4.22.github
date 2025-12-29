"""
Sample messages for testing Wolf Trading Bot.
"""

# Example FREE signal
FREE_SIGNAL_EXAMPLE = """
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
"""

# Example FREE signal - SHORT
FREE_SIGNAL_SHORT = """
👍THE WOLF SCALPER👍

✔️COIN NAME: BTCUSDT

LEVERAGE: 50x

🔽TRADE TYPE: SHORT 📉

✔️ENTRY PRICE (42500-42700)

☄️TAKE-PROFITS

1️⃣ 42000
2️⃣ 41500
3️⃣ 41000

STOP LOSS: 43200
"""

# Example FREE signal - Alternative format
FREE_SIGNAL_ALT = """
🐺 WOLF FREE SIGNAL 🐺

#BEAT/USDT

LONG

Entry: 0.0025 - 0.0026

TP1: 0.0027
TP2: 0.0028
TP3: 0.0030

SL: 0.0023
"""

# VIP Signal Caption (from forwarded message)
VIP_SIGNAL_CAPTION = """
#WOLF_VIP_SIGNAL 📡

📡 WOLF PREMIUM TRADE RESULT

💵 #ICNT/USDT Take-Profit Target 1 🎯 Achieved ALHUMDULILAH with the Profit of: +147.52% CLOSE 90% NOW 📈
Period: 04 Hours 51 Minutes ...

JOIN BITUNIX NOWW 🔥
🦊 @Wolfscalperadmin ✅
#WE_STAND_WITH_PALESTINE
"""

# VIP Signal Caption - First post (tradeable)
VIP_SIGNAL_FIRST_POST = """
#WOLF_VIP_SIGNAL 📡

💵 #ICNT/USDT
Direction: LONG
Leverage: 50x

Entry: 0.4623

JOIN BITUNIX NOW 🔥
"""

# Results/Promotional post (should be ignored)
RESULTS_POST = """
📊 DAILY TRADING RESULTS 📊

🎯 WOLF PREMIUM TRADE RESULTS

Total Signals: 15
Winners: 13
Losers: 2

Total Profit: +847%

JOIN VIP NOW 🔥
"""

# Another promotional post
PROMO_POST = """
🐺 JOIN WOLF VIP 🐺

✅ 95% Accuracy
✅ 24/7 Signals
✅ Personal Support

JOIN NOW: t.me/wolfvip
"""

# OCR text simulation (from Bitunix Pro screenshot)
OCR_TEXT_BITUNIX = """
Bitunix Pro

ICNTUSDT | Long 50X
+147.52%

Entry Price 0.4623
Last Price 0.4760
"""

# OCR text - SHORT position
OCR_TEXT_SHORT = """
Bitunix Pro

BTCUSDT | Short 25X
-5.23%

Entry Price 43500
Last Price 43720
"""

# Invalid message (should be ignored)
INVALID_MESSAGE = """
Hello everyone! How is the market today?

Check out this new coin 🚀🚀🚀
"""

# Message with similar keywords but not a signal
NOT_A_SIGNAL = """
I'm currently LONG on my analysis of the market.
The ENTRY into crypto should be considered carefully.
Always set a STOP LOSS mentally.
"""
