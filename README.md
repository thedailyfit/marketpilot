# MARKETPILOT AI - Algorithmic Trading Engine

## Overview
MarketPilot AI is an advanced algorithmic trading system designed for the NSE Futures & Options market. It features a microservice-like agent architecture (Supervisor, MarketData, Strategy, Risk, Execution, Accounting) and a real-time command dashboard.

## Features
- **Live Trading**: Integrated with Upstox API for real-time data and execution.
- **Paper Trading**: Realistic simulation environment with 10ms latency mock.
- **Backtesting**: High-speed replay engine (1000x) for strategy verification.
- **Deep Scan**: Multi-timeframe trend analysis and Option Chain decoding.
- **Command Dashboard**: "Hive" interface for monitoring and manual intervention.

## Quick Start (Deployment)

1. **Install Dependencies**
   ```powershell
   py -m pip install -r requirements.txt
   ```

2. **Configure Credentials**
   - Create a `.env` file in the root directory.
   - Add your Upstox credentials:
     ```
     API_KEY=your_api_key
     API_SECRET=your_api_secret
     ACCESS_TOKEN=your_generated_access_token
     REDIRECT_URI=http://localhost:8000/callback
     ```
   - *Tip: Use `utils/get_access_token.py` if you need to generate a token.*

3. **Launch Engine**
   Double-click **`start_engine.bat`**
   *Or run:*
   ```powershell
   py -m uvicorn new_server:app --reload
   ```

4. **Access Dashboard**
   Open your browser to: **[http://localhost:8000/dashboard](http://localhost:8000/dashboard)**

## Operations
- **Switch Modes**: Use the Dashboard header tabs to toggle between **Simulation** and **Real Execution**.
- **Deep Scan**: Click "RUN DEEP SCAN" to analyze market conditions before activating.
- **Initialize**: Click "INITIALIZE AGENT" to start the strategy loop.
- **Emergency Stop**: Click "SYSTEM HALT" to instantly stop all loops and cancel pending orders.

## Verification Tools
- **Live Order Test**: Run `py utils/test_live_order.py` to place a single 1-qty Equity order for API verification.
- **Backtest**: Run `py utils/run_backtest.py` to validate strategy logic.

---
**Disclaimer**: Use at your own risk. Algorithmic trading involves significant financial risk.
