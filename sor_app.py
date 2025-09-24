import os, time, math, streamlit as st, ccxt

# ----------------- Config -----------------
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "BTC/USDT")
THROUGH_BPS = 3.0            # cross for marketable-limit
ORDER_WAIT_SECONDS = 0.35     # brief wait then cancel
USE_FOK_FIRST = True          # FOK -> IOC -> plain limit

EXCHS = {
    "gateio": {"label": "Gate.io", "env": "GATE", "klass": ccxt.gateio},
    "mexc":   {"label": "MEXC",   "env": "MEXC", "klass": ccxt.mexc},
}

# --------------- Helpers ------------------
def build_client(k):
    spec = EXCHS[k]
    ex = spec["klass"]({
        "apiKey": os.getenv(f"{spec['env']}_API_KEY",""),
        "secret": os.getenv(f"{spec['env']}_API_SECRET",""),
        "enableRateLimit": True,
        "timeout": 10000,
    })
    ex.options = ex.options or {}
    ex.options["defaultType"] = "spot"
    return ex

def load_markets(ex):
    try: ex.load_markets(reload=True)
    except Exception as e: st.warning(f"[{ex.id}] load_markets failed: {e}")

def taker_fee(mkt): 
    try: return float(mkt.get("taker", 0.001))
    except: return 0.001

def price_to_precision(ex, sym, px):
    try: return float(ex.price_to_precision(sym, px))
    except: return float(px)

def amount_to_precision(ex, sym, amt):
    try: return float(ex.amount_to_precision(sym, amt))
    except: return float(amt)

def clamp_amount(mkt, amt):
    lim = (mkt or {}).get("limits", {})
    mn = lim.get("amount", {}).get("min"); mx = lim.get("amount", {}).get("max")
    if mn is not None and amt < float(mn): return 0.0
    if mx is not None and amt > float(mx): return float(mx)
    return float(amt)

def fetch_entry_tob_with_qty(ex, symbol, side):
    px, qty = 0.0, 0.0
    # ticker first
    try:
        t = ex.fetch_ticker(symbol)
        bid, ask = float(t.get("bid") or 0), float(t.get("ask") or 0)
        bidVol, askVol = float(t.get("bidVolume") or 0), float(t.get("askVolume") or 0)
        if side=="buy" and ask>0: px, qty = ask, askVol
        elif side=="sell" and bid>0: px, qty = bid, bidVol
    except: pass
    # fallback to tiny orderbook
    if px<=0 or qty<=0:
        try:
            ob = ex.fetch_order_book(symbol, limit=5)
            bids, asks = ob.get("bids") or [], ob.get("asks") or []
            if side=="buy" and asks: px, qty = float(asks[0][0]), float(asks[0][1])
            if side=="sell" and bids: px, qty = float(bids[0][0]), float(bids[0][1])
        except: pass
    return px, qty

def depth_within_bps(ex, symbol, side, taker, bps):
    try: ob = ex.fetch_order_book(symbol, limit=25)
    except Exception as e:
        st.warning(f"[{ex.id}] depth fetch failed: {e}"); return 0.0, 0.0
    bids, asks = ob.get("bids") or [], ob.get("asks") or []
    if side=="buy":
        if not asks: return 0.0, 0.0
        tob = float(asks[0][0]); cap = tob*(1+bps/1e4)
        qty, cost = 0.0, 0.0
        for px, sz in asks:
            px, sz = float(px), float(sz)
            if px>cap: break
            qty += sz; cost += sz*px
        vwap = (cost/qty) if qty>0 else 0.0
        return qty, vwap*(1+taker) if vwap>0 else 0.0
    else:
        if not bids: return 0.0, 0.0
        tob = float(bids[0][0]); cap = tob*(1-bps/1e4)
        qty, rev = 0.0, 0.0
        for px, sz in bids:
            px, sz = float(px), float(sz)
            if px<cap: break
            qty += sz; rev += sz*px
        vwap = (rev/qty) if qty>0 else 0.0
        return qty, vwap*(1-taker) if vwap>0 else 0.0

def place_marketable_limit(ex, symbol, side, qty, guard_px, cross_bps=THROUGH_BPS, fok_first=True):
    if guard_px<=0: raise ValueError("No guard TOB")
    px = guard_px*(1+cross_bps/1e4 if side=="buy" else 1-cross_bps/1e4)
    px = price_to_precision(ex, symbol, px)
    chain = [{"timeInForce":"FOK"},{"timeInForce":"IOC"},{}] if fok_first else [{"timeInForce":"IOC"},{}]
    last_err=None
    for params in chain:
        try:
            o = ex.create_order(symbol, "limit", side, qty, px, params=params)
            time.sleep(ORDER_WAIT_SECONDS)
            info = ex.fetch_order(o.get("id"), symbol)
            filled = float((info or {}).get("filled") or 0.0)
            avg = (info or {}).get("average")
            if not avg:
                cost = (info or {}).get("cost")
                if cost and filled>0: avg = float(cost)/filled
            avg = float(avg or 0.0)
            if (info or {}).get("status") in ("open","partially_filled"):
                try: ex.cancel_order(o.get("id"), symbol)
                except: pass
            return o, avg, filled
        except Exception as e:
            last_err=e
            continue
    raise last_err

def fmt(x, d=8): 
    try: return f"{float(x):.{d}f}"
    except: return "-"

# --------------- UI ---------------------
st.set_page_config(page_title="SOR — Gate.io + MEXC", layout="centered")
st.title("SOR — Gate.io + MEXC (Spot)")
st.caption("Local UI • API keys stay on your machine • Dry-run by default")

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

if btn_fetch:
    rows = []
    ex_map = {}
    for k in EXCHS:
        ex = build_client(k); ex_map[k]=ex
        sym = (ovr_gate if (k=="gateio" and ovr_gate) else ovr_mexc if (k=="mexc" and ovr_mexc) else symbol)
        load_markets(ex)
        mkt = ex.markets.get(sym)
        if not mkt or mkt.get("active") is False:
            st.warning(f"{EXCHS[k]['label']}: '{sym}' not listed/active")
            continue
        px, qty = fetch_entry_tob_with_qty(ex, sym, side)
        tk = taker_fee(mkt)
        eff = px*(1+tk) if side=="buy" else px*(1-tk)
        row = {"k":k,"label":EXCHS[k]["label"],"sym":sym,"px":px,"qty":qty,"taker":tk,"eff":eff}
        if show_depth:
            mx, vwap = depth_within_bps(ex, sym, side, tk, bps)
            row["mx"]=mx; row["vwap"]=vwap
        rows.append(row)

    if not rows:
        st.stop()

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
            if p["desired"] <= 0: continue
            ex = ex_map[p["k"]]; sym = p["sym"]
            mkt = ex.markets.get(sym)
            qty = amount_to_precision(ex, sym, clamp_amount(mkt, p["desired"]))
            if qty <= 0:
                results.append({"Venue": EXCHS[p["k"]]["label"], "Error":"amount_below_min"}); continue
            guard = p["guard"]
            if guard <= 0:
                results.append({"Venue": EXCHS[p["k"]]["label"], "Error":"no_guard_price"}); continue

            if dry:
                results.append({
                    "Venue": EXCHS[p["k"]]["label"], "Symbol": sym,
                    "Placed Qty": qty, "Guard TOB": guard,
                    "Avg Fill": 0.0, "Filled Qty": 0.0, "Slippage (bps)": 0.0,
                    "Note": "DRY-RUN"
                })
                continue

            try:
                order, avg, filled = place_marketable_limit(ex, sym, side, qty, guard)
                slip = ((avg-guard)/guard*1e4) if (avg>0 and guard>0 and side=="buy") else ((guard-avg)/guard*1e4 if (avg>0 and guard>0) else 0.0)
                results.append({
                    "Venue": EXCHS[p["k"]]["label"], "Symbol": sym,
                    "Placed Qty": qty, "Guard TOB": guard,
                    "Avg Fill": avg, "Filled Qty": filled, "Slippage (bps)": round(slip,2)
                })
            except Exception as e:
                results.append({"Venue": EXCHS[p["k"]]["label"], "Symbol": sym, "Error": str(e)})

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
    # Close clients
    for ex in ex_map.values():
        try: ex.close()
        except: pass
