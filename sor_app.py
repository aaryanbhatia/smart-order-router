import os, time, math, streamlit as st, requests
import json

# ----------------- Config -----------------
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "BTC/USDT")
THROUGH_BPS = 3.0            # cross for marketable-limit
ORDER_WAIT_SECONDS = 0.35     # brief wait then cancel
USE_FOK_FIRST = True          # FOK -> IOC -> plain limit

# Cloud API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://smart-order-router.onrender.com")

# Simulated exchanges for display
EXCHS = {
    "gateio": {"label": "Gate.io", "env": "GATE"},
    "mexc":   {"label": "MEXC",   "env": "MEXC"},
}

# --------------- API Helpers ------------------
def call_api(endpoint, method="GET", data=None):
    """Call the cloud API"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def taker_fee(venue): 
    # Default taker fees for different venues
    fees = {"gateio": 0.002, "mexc": 0.002, "kucoin": 0.001, "bitget": 0.001}
    return fees.get(venue.lower(), 0.001)

def price_to_precision(price, decimals=8):
    try: return round(float(price), decimals)
    except: return float(price)

def amount_to_precision(amount, decimals=8):
    try: return round(float(amount), decimals)
    except: return float(amount)

def clamp_amount(amount, min_amount=0.001, max_amount=1000000):
    try:
        amt = float(amount)
        if amt < min_amount: return 0.0
        if amt > max_amount: return max_amount
        return amt
    except: return 0.0

def fetch_entry_tob_with_qty(venue, symbol, side):
    """Fetch top of book data from cloud API"""
    try:
        # Convert BTC/USDT to BTCUSDT for API
        api_symbol = symbol.replace("/", "")
        prices = call_api(f"/prices/{api_symbol}")
        if not prices:
            return 0.0, 0.0
        
        # Find data for the specific venue
        for price_data in prices:
            if price_data.get("venue", "").lower() == venue.lower():
                if side == "buy":
                    px = price_data.get("ask_price", 0)
                    qty = price_data.get("ask_quantity", 0)
                else:
                    px = price_data.get("bid_price", 0)
                    qty = price_data.get("bid_quantity", 0)
                return float(px), float(qty)
        
        # Fallback to first available data
        price_data = prices[0]
        if side == "buy":
            px = price_data.get("ask_price", 0)
            qty = price_data.get("ask_quantity", 0)
        else:
            px = price_data.get("bid_price", 0)
            qty = price_data.get("bid_quantity", 0)
        
        return float(px), float(qty)
    except Exception as e:
        st.error(f"Failed to fetch prices for {venue}: {e}")
        return 0.0, 0.0

def depth_within_bps(venue, symbol, side, taker, bps):
    """Calculate depth within basis points from cloud API"""
    try:
        # Convert BTC/USDT to BTCUSDT for API
        api_symbol = symbol.replace("/", "")
        prices = call_api(f"/prices/{api_symbol}")
        if not prices:
            return 0.0, 0.0
        
        # Find data for the specific venue
        price_data = None
        for p in prices:
            if p.get("venue", "").lower() == venue.lower():
                price_data = p
                break
        
        if not price_data:
            price_data = prices[0]  # Fallback to first available
        
        base_price = price_data.get("ask_price" if side == "buy" else "bid_price", 0)
        base_qty = price_data.get("ask_quantity" if side == "buy" else "bid_quantity", 0)
        
        # Simulate depth calculation
        depth_factor = 1 + (bps / 10000)
        max_qty = float(base_qty) * depth_factor
        vwap = float(base_price) * (1 + taker if side == "buy" else 1 - taker)
        
        return max_qty, vwap
    except Exception as e:
        st.warning(f"[{venue}] depth calculation failed: {e}")
        return 0.0, 0.0

def place_marketable_limit(venue, symbol, side, qty, guard_px, cross_bps=THROUGH_BPS, fok_first=True):
    """Place order via cloud API"""
    if guard_px <= 0: 
        raise ValueError("No guard TOB")
    
    px = guard_px * (1 + cross_bps/10000 if side == "buy" else 1 - cross_bps/10000)
    px = price_to_precision(px)
    
    try:
        order_data = {
            "symbol": symbol,
            "side": side,
            "order_type": "limit",
            "quantity": qty,
            "price": px
        }
        
        result = call_api("/orders", method="POST", data=order_data)
        if result:
            return result, result.get("average_price", px), result.get("total_filled", qty)
        else:
            raise Exception("Failed to place order")
    except Exception as e:
        st.error(f"Order placement failed: {e}")
        raise e

def fmt(x, d=8): 
    try: return f"{float(x):.{d}f}"
    except: return "-"

# --------------- UI ---------------------
st.set_page_config(page_title="SOR — Smart Order Router", layout="centered")
st.title("SOR — Smart Order Router")
st.caption("Cloud API • Real-time trading • Multi-exchange support")

# API Status Check
with st.sidebar:
    st.header("API Status")
    health = call_api("/health")
    if health:
        st.success("✅ API Connected")
        st.write(f"Status: {health.get('status', 'Unknown')}")
    else:
        st.error("❌ API Disconnected")
        st.write("Make sure your cloud API is running")

colA, colB, colC = st.columns([1,1,1])
with colA:
    symbol = st.text_input("Symbol", value=DEFAULT_SYMBOL).upper().strip()
with colB:
    side = st.radio("Side", ["buy","sell"], horizontal=True)
with colC:
    show_depth = st.checkbox("Depth (bps)", value=True)

bps = st.slider("Depth budget (bps)", 0, 200, 20, 1, disabled=not show_depth)
st.divider()

# Optional per-exchange symbol overrides (for mismatched names)
with st.expander("Per-exchange symbol overrides (optional)"):
    ovr_gate = st.text_input("Gate.io override", value="")
    ovr_mexc = st.text_input("MEXC override", value="")

btn_fetch = st.button("Fetch quotes")

# Initialize session state
if 'price_data' not in st.session_state:
    st.session_state.price_data = None
if 'rows' not in st.session_state:
    st.session_state.rows = []

if btn_fetch:
    # Fetch prices from cloud API
    # Convert BTC/USDT to BTCUSDT for API
    api_symbol = symbol.replace("/", "")
    prices = call_api(f"/prices/{api_symbol}")
    
    if not prices:
        st.error("Failed to fetch prices from cloud API")
        st.stop()
    
    # Store in session state
    st.session_state.price_data = prices
    
    # Process each venue's data
    rows = []
    for price_data in prices:
        venue = price_data.get("venue", "unknown")
        px, qty = fetch_entry_tob_with_qty(venue, symbol, side)
        tk = taker_fee(venue)
        eff = px*(1+tk) if side=="buy" else px*(1-tk)
        
        row = {
            "k": venue,
            "label": venue.upper(),
            "sym": symbol,
            "px": px,
            "qty": qty,
            "taker": tk,
            "eff": eff
        }
        
        if show_depth:
            mx, vwap = depth_within_bps(venue, symbol, side, tk, bps)
            row["mx"] = mx
            row["vwap"] = vwap
        
        rows.append(row)
    
    # Store rows in session state
    st.session_state.rows = rows

# Use stored data if available
if st.session_state.rows:
    rows = st.session_state.rows

    st.subheader("Fast snapshot (your side)")
    st.table([{
        "Venue": r["label"],
        "Symbol": r["sym"],
        "Entry TOB Price": fmt(r["px"]),
        "Entry TOB Quantity": fmt(r["qty"]),
        "Taker Fee": fmt(r["taker"],4),
        "Effective Entry Price": fmt(r["eff"])
    } for r in rows])

    if show_depth:
        st.subheader(f"Depth within {bps} bps (VWAP incl. taker)")
        st.table([{
            "Venue": r["label"], "Symbol": r["sym"],
            "Max Qty @bps": fmt(r.get("mx",0)),
            "Effective VWAP @bps": fmt(r.get("vwap",0))
        } for r in rows])

    st.divider()
    st.subheader("Manual quantities (per venue)")
    cols = st.columns(len(rows))
    plan = []
    for i, r in enumerate(rows):
        with cols[i]:
            q = st.number_input(f"{r['label']} qty", min_value=0.0, value=0.0, step=1.0, key=f"qty_{r['k']}")
            if show_depth: st.caption(f"Tip: ≤ {fmt(r.get('mx',0),4)} to stay within budget")
            plan.append({"k":r["k"],"sym":r["sym"],"guard":r["px"],"desired":q})

    dry = st.toggle("DRY-RUN (no orders)", value=True)
    if st.button("Execute (marketable-limit)"):
        results = []
        for p in plan:
            if p["desired"] <= 0: 
                continue
            
            venue = p["k"]
            sym = p["sym"]
            qty = amount_to_precision(clamp_amount(p["desired"]))
            
            if qty <= 0:
                results.append({"Venue": venue.upper(), "Error":"amount_below_min"})
                continue
            
            guard = p["guard"]
            if guard <= 0:
                results.append({"Venue": venue.upper(), "Error":"no_guard_price"})
                continue

            if dry:
                results.append({
                    "Venue": venue.upper(), 
                    "Symbol": sym,
                    "Placed Qty": qty, 
                    "Guard TOB": guard,
                    "Avg Fill": 0.0, 
                    "Filled Qty": 0.0, 
                    "Slippage (bps)": 0.0,
                    "Note": "DRY-RUN"
                })
                continue

            try:
                order, avg, filled = place_marketable_limit(venue, sym, side, qty, guard)
                slip = ((avg-guard)/guard*10000) if (avg>0 and guard>0 and side=="buy") else ((guard-avg)/guard*10000 if (avg>0 and guard>0) else 0.0)
                results.append({
                    "Venue": venue.upper(), 
                    "Symbol": sym,
                    "Placed Qty": qty, 
                    "Guard TOB": guard,
                    "Avg Fill": avg, 
                    "Filled Qty": filled, 
                    "Slippage (bps)": round(slip,2)
                })
            except Exception as e:
                results.append({"Venue": venue.upper(), "Symbol": sym, "Error": str(e)})

        if not results:
            st.warning("Enter a positive quantity for at least one venue.")
        else:
            st.subheader("Execution report")
            st.table(results)
            tot_filled = sum((r.get("Filled Qty") or 0.0) for r in results if "Filled Qty" in r)
            tot_notional = 0.0
            for r in results:
                if "Filled Qty" in r:
                    px = r.get("Avg Fill") or r.get("Guard TOB") or 0.0
                    tot_notional += (r.get("Filled Qty") or 0.0) * px
            overall_avg = (tot_notional/tot_filled) if tot_filled>0 else 0.0
            st.caption(f"Overall filled: {fmt(tot_filled)} units @ average {fmt(overall_avg)}")

# Footer
st.divider()
st.caption(f"Connected to: {API_BASE_URL}")
st.caption("Smart Order Router - Cloud Deployment")
