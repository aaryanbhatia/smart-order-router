"""
Streamlit frontend for Smart Order Router
Connects to the cloud API
"""

import streamlit as st
import requests
import json
from datetime import datetime

# Configure Streamlit
st.set_page_config(
    page_title="SOR — Smart Order Router", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# API Configuration
API_BASE_URL = "https://smart-order-router.onrender.com"

def call_api(endpoint, method="GET", data=None):
    """Call the cloud API"""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

# Main UI
st.title("SOR — Smart Order Router")
st.caption("Cloud API • Real-time trading • Multi-exchange support")

# Sidebar for API status
with st.sidebar:
    st.header("API Status")
    health = call_api("/health")
    if health:
        st.success("✅ API Connected")
        st.write(f"Status: {health.get('status', 'Unknown')}")
        st.write(f"Last Update: {health.get('timestamp', 'Unknown')}")
    else:
        st.error("❌ API Disconnected")

# Main trading interface
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    symbol = st.text_input("Symbol", value="BTC/USDT").upper().strip()

with col2:
    side = st.radio("Side", ["buy", "sell"], horizontal=True)

with col3:
    show_depth = st.checkbox("Depth (bps)", value=True)

# Depth budget slider
bps = st.slider("Depth budget (bps)", 0, 200, 20, 1, disabled=not show_depth)
st.divider()

# Per-exchange symbol overrides
with st.expander("Per-exchange symbol overrides (optional)"):
    ovr_gate = st.text_input("Gate.io override", value="")
    ovr_mexc = st.text_input("MEXC override", value="")

# Fetch quotes button
if st.button("Fetch quotes", type="primary"):
    with st.spinner("Fetching quotes..."):
        # Get prices from API
        prices = call_api(f"/prices/{symbol}")
        
        if prices:
            st.subheader("Fast snapshot (your side)")
            
            # Create data for display
            data = []
            for price in prices:
                data.append({
                    "Venue": price.get("venue", "Unknown"),
                    "Symbol": price.get("symbol", symbol),
                    "Entry TOB Price": f"{price.get('bid_price', 0):.8f}",
                    "Entry TOB Quantity": f"{price.get('bid_quantity', 0):.8f}",
                    "Taker Fee": "0.0020",
                    "Effective Entry Price": f"{price.get('effective_bid', 0):.8f}"
                })
            
            if data:
                st.table(data)
            else:
                st.warning("No price data available")
        else:
            st.error("Failed to fetch quotes")

# Order placement section
st.divider()
st.subheader("Place Order")

col1, col2 = st.columns([2, 1])

with col1:
    order_quantity = st.number_input("Quantity", min_value=0.0, value=0.001, step=0.001, format="%.6f")

with col2:
    order_price = st.number_input("Price (for limit orders)", min_value=0.0, value=0.0, step=0.01, format="%.2f")

if st.button("Place Order", type="primary"):
    if order_quantity > 0:
        order_data = {
            "symbol": symbol,
            "side": side,
            "order_type": "market" if order_price == 0 else "limit",
            "quantity": order_quantity,
            "price": order_price if order_price > 0 else None
        }
        
        with st.spinner("Placing order..."):
            result = call_api("/orders", method="POST", data=order_data)
            
            if result:
                st.success("Order placed successfully!")
                st.json(result)
            else:
                st.error("Failed to place order")
    else:
        st.warning("Please enter a valid quantity")

# System information
st.divider()
st.subheader("System Information")

if st.button("Get System Stats"):
    stats = call_api("/system/stats")
    if stats:
        st.json(stats)
    else:
        st.error("Failed to get system stats")

# Footer
st.divider()
st.caption(f"Connected to: {API_BASE_URL}")
st.caption("Smart Order Router - Cloud Deployment")
