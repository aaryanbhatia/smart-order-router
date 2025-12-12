"""
REST API Server for Smart Order Router
Provides HTTP endpoints for external access to SOR functionality
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Import models and SOR components
try:
    from models import OrderSide, OrderType, ExecutionResult
    from smart_order_router import SmartOrderRouter
except ImportError:
    # Fallback for missing modules
    from enum import Enum
    from decimal import Decimal
    from typing import Optional
    
    class OrderSide(str, Enum):
        BUY = "buy"
        SELL = "sell"
    
    class OrderType(str, Enum):
        MARKET = "market"
        LIMIT = "limit"
    
    class ExecutionResult:
        def __init__(self, success=False, order_id=None, total_filled=0, average_price=None, total_cost=0, executions=None):
            self.success = success
            self.order_id = order_id or "test-order-id"
            self.total_filled = total_filled
            self.average_price = average_price
            self.total_cost = total_cost
            self.executions = executions or []
    
    class SmartOrderRouter:
        async def initialize(self): pass
        async def start(self): pass
        async def stop(self): pass
        async def place_order(self, **kwargs): return ExecutionResult(success=True)
        async def get_best_prices(self, symbol): return {"best_bid": 50000, "best_ask": 50001}
        async def get_arbitrage_opportunities(self, symbol, min_spread=0.001): return []
        async def get_statistics(self): return {"uptime": 0, "venues": {}, "total_orders": 0, "success_rate": 1.0, "average_execution_time": 0}
        async def get_risk_summary(self): return {}
from config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
DATABASE_URL = config.database_url if hasattr(config, 'database_url') else "postgresql://sor_user:sor_password@localhost:5432/sor_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FastAPI app
app = FastAPI(
    title="Smart Order Router API",
    description="REST API for cross-exchange trading and order routing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Global SOR instance
sor_instance: Optional[SmartOrderRouter] = None

# Pydantic models
class OrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair (e.g., BTC/USDT)")
    side: str = Field(..., description="Order side: buy or sell")
    order_type: str = Field(..., description="Order type: market or limit")
    quantity: float = Field(..., gt=0, description="Order quantity")
    price: Optional[float] = Field(None, gt=0, description="Limit price for limit orders")
    max_slippage: Optional[float] = Field(None, ge=0, le=1, description="Maximum slippage (0-1)")
    user_id: Optional[str] = Field(None, description="User identifier")

class OrderResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float]
    status: str
    total_filled: float
    average_price: Optional[float]
    total_cost: float
    created_at: datetime
    executions: List[Dict[str, Any]]

class PriceData(BaseModel):
    symbol: str
    venue: str
    bid_price: float
    ask_price: float
    bid_quantity: float
    ask_quantity: float
    spread_bps: float
    effective_bid: float
    effective_ask: float
    timestamp: datetime

class ArbitrageOpportunity(BaseModel):
    symbol: str
    buy_venue: str
    sell_venue: str
    buy_price: float
    sell_price: float
    spread_bps: float
    potential_profit: float
    timestamp: datetime

class RiskMetrics(BaseModel):
    user_id: Optional[str]
    symbol: Optional[str]
    total_exposure: float
    daily_volume: float
    position_size: float
    unrealized_pnl: float
    realized_pnl: float
    max_drawdown: float
    timestamp: datetime

class SystemHealth(BaseModel):
    status: str
    uptime: float
    active_venues: int
    total_orders: int
    success_rate: float
    average_execution_time: float
    last_updated: datetime

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Dependency to get SOR instance
async def get_sor():
    global sor_instance
    if sor_instance is None:
        sor_instance = SmartOrderRouter()
        await sor_instance.initialize()
        await sor_instance.start()
    return sor_instance


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize SOR on startup"""
    global sor_instance
    try:
        sor_instance = SmartOrderRouter()
        await sor_instance.initialize()
        await sor_instance.start()
        logger.info("SOR initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize SOR: {e}")
        raise

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global sor_instance
    if sor_instance:
        await sor_instance.stop()
        logger.info("SOR stopped")

# Health check endpoint
@app.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Health check endpoint"""
    try:
        sor = await get_sor()
        stats = await sor.get_statistics()
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime": stats.get("uptime", 0),
            "active_venues": len(stats.get("venues", {})),
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

# Order endpoints
@app.post("/orders", response_model=OrderResponse)
async def create_order(
    order_request: OrderRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """Create a new order"""
    try:
        sor = await get_sor()
        
        # Convert to Decimal for precision
        quantity = Decimal(str(order_request.quantity))
        price = Decimal(str(order_request.price)) if order_request.price else None
        max_slippage = Decimal(str(order_request.max_slippage)) if order_request.max_slippage else None
        
        # Convert side and order_type to enums
        side = OrderSide.BUY if order_request.side.lower() == "buy" else OrderSide.SELL
        order_type = OrderType.MARKET if order_request.order_type.lower() == "market" else OrderType.LIMIT
        
        # Place order
        result = await sor.place_order(
            symbol=order_request.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            max_slippage=max_slippage,
            user_id=order_request.user_id
        )
        
        # Store order in database
        # Handle None values safely
        total_filled = float(result.total_filled) if result.total_filled is not None else 0.0
        average_price = float(result.average_price) if result.average_price is not None else None
        total_cost = float(result.total_cost) if result.total_cost is not None else 0.0
        
        order_data = {
            "id": str(result.order_id),
            "symbol": order_request.symbol,
            "side": order_request.side,
            "order_type": order_request.order_type,
            "quantity": float(quantity),
            "price": float(price) if price else None,
            "status": "filled" if result.success else "failed",
            "total_filled": total_filled,
            "average_price": average_price,
            "total_cost": total_cost,
            "max_slippage": float(max_slippage) if max_slippage else None,
            "user_id": order_request.user_id,
            "created_at": datetime.utcnow()
        }
        
        # Insert order
        db.execute(text("""
            INSERT INTO orders (id, symbol, side, order_type, quantity, price, status, 
                              total_filled, average_price, total_cost, max_slippage, user_id, created_at)
            VALUES (:id, :symbol, :side, :order_type, :quantity, :price, :status,
                    :total_filled, :average_price, :total_cost, :max_slippage, :user_id, :created_at)
        """), order_data)
        
        # Store executions
        for execution in result.executions:
            exec_data = {
                "order_id": str(result.order_id),
                "venue": execution.get("venue", ""),
                "venue_order_id": execution.get("venue_order_id", ""),
                "quantity": float(execution.get("quantity", 0)),
                "price": float(execution.get("price", 0)),
                "filled_quantity": float(execution.get("filled_quantity", 0)),
                "average_price": float(execution.get("average_price", 0)) if execution.get("average_price") else None,
                "status": execution.get("status", "pending"),
                "execution_time_ms": execution.get("execution_time_ms", 0),
                "slippage_bps": float(execution.get("slippage_bps", 0)) if execution.get("slippage_bps") else None,
                "created_at": datetime.utcnow()
            }
            
            db.execute(text("""
                INSERT INTO order_executions (order_id, venue, venue_order_id, quantity, price,
                                            filled_quantity, average_price, status, execution_time_ms, slippage_bps, created_at)
                VALUES (:order_id, :venue, :venue_order_id, :quantity, :price,
                        :filled_quantity, :average_price, :status, :execution_time_ms, :slippage_bps, :created_at)
            """), exec_data)
        
        db.commit()
        
        # Handle None values safely for response
        total_filled = float(result.total_filled) if result.total_filled is not None else 0.0
        average_price = float(result.average_price) if result.average_price is not None else None
        total_cost = float(result.total_cost) if result.total_cost is not None else 0.0
        
        return OrderResponse(
            order_id=str(result.order_id),
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            quantity=float(quantity),
            price=float(price) if price else None,
            status="filled" if result.success else "failed",
            total_filled=total_filled,
            average_price=average_price,
            total_cost=total_cost,
            created_at=datetime.utcnow(),
            executions=result.executions or []
        )
        
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        logger.error(f"Failed to create order: {error_msg}")
        logger.exception(e)  # Log full traceback for debugging
        # Return more detailed error information
        raise HTTPException(
            status_code=500, 
            detail=f"Order placement failed: {error_msg}. Check logs for details."
        )

@app.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: str, db = Depends(get_db)):
    """Get order details"""
    try:
        result = db.execute(text("""
            SELECT o.*, 
                   COALESCE(json_agg(
                       json_build_object(
                           'venue', e.venue,
                           'venue_order_id', e.venue_order_id,
                           'quantity', e.quantity,
                           'price', e.price,
                           'filled_quantity', e.filled_quantity,
                           'average_price', e.average_price,
                           'status', e.status,
                           'execution_time_ms', e.execution_time_ms,
                           'slippage_bps', e.slippage_bps
                       )
                   ) FILTER (WHERE e.id IS NOT NULL), '[]') as executions
            FROM orders o
            LEFT JOIN order_executions e ON o.id = e.order_id
            WHERE o.id = :order_id
            GROUP BY o.id
        """), {"order_id": order_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return OrderResponse(
            order_id=str(result.id),
            symbol=result.symbol,
            side=result.side,
            order_type=result.order_type,
            quantity=float(result.quantity),
            price=float(result.price) if result.price else None,
            status=result.status,
            total_filled=float(result.total_filled),
            average_price=float(result.average_price) if result.average_price else None,
            total_cost=float(result.total_cost),
            created_at=result.created_at,
            executions=result.executions or []
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    user_id: Optional[str] = Query(None),
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
):
    """List orders with optional filters"""
    try:
        where_conditions = []
        params = {"limit": limit, "offset": offset}
        
        if user_id:
            where_conditions.append("o.user_id = :user_id")
            params["user_id"] = user_id
        
        if symbol:
            where_conditions.append("o.symbol = :symbol")
            params["symbol"] = symbol
            
        if status:
            where_conditions.append("o.status = :status")
            params["status"] = status
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        result = db.execute(text(f"""
            SELECT o.*, 
                   COALESCE(json_agg(
                       json_build_object(
                           'venue', e.venue,
                           'venue_order_id', e.venue_order_id,
                           'quantity', e.quantity,
                           'price', e.price,
                           'filled_quantity', e.filled_quantity,
                           'average_price', e.average_price,
                           'status', e.status,
                           'execution_time_ms', e.execution_time_ms,
                           'slippage_bps', e.slippage_bps
                       )
                   ) FILTER (WHERE e.id IS NOT NULL), '[]') as executions
            FROM orders o
            LEFT JOIN order_executions e ON o.id = e.order_id
            WHERE {where_clause}
            GROUP BY o.id
            ORDER BY o.created_at DESC
            LIMIT :limit OFFSET :offset
        """), params).fetchall()
        
        orders = []
        for row in result:
            orders.append(OrderResponse(
                order_id=str(row.id),
                symbol=row.symbol,
                side=row.side,
                order_type=row.order_type,
                quantity=float(row.quantity),
                price=float(row.price) if row.price else None,
                status=row.status,
                total_filled=float(row.total_filled),
                average_price=float(row.average_price) if row.average_price else None,
                total_cost=float(row.total_cost),
                created_at=row.created_at,
                executions=row.executions or []
            ))
        
        return orders
        
    except Exception as e:
        logger.error(f"Failed to list orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Price data endpoints
@app.get("/prices/{symbol}")
async def get_prices(symbol: str):
    """Get current prices for a symbol across all venues"""
    try:
        sor = await get_sor()
        price_data = await sor.get_best_prices(symbol)
        
        # Convert to PriceData format
        prices = []
        if price_data:
            # Create individual entries for each exchange that has data
            for exchange_name, exchange in sor.exchanges.items():
                try:
                    # Convert symbol format based on exchange
                    if exchange_name == 'gateio':
                        if "/" in symbol:
                            exchange_symbol = symbol
                        elif symbol.endswith("USDT"):
                            exchange_symbol = symbol.replace("USDT", "/USDT")
                        elif symbol.endswith("BTC"):
                            exchange_symbol = symbol.replace("BTC", "/BTC")
                        elif symbol.endswith("ETH"):
                            exchange_symbol = symbol.replace("ETH", "/ETH")
                        else:
                            exchange_symbol = symbol
                    elif exchange_name == 'kucoin':
                        if "/" in symbol:
                            exchange_symbol = symbol.replace("/", "-")
                        elif symbol.endswith("USDT"):
                            exchange_symbol = symbol.replace("USDT", "-USDT")
                        elif symbol.endswith("BTC"):
                            exchange_symbol = symbol.replace("BTC", "-BTC")
                        elif symbol.endswith("ETH"):
                            exchange_symbol = symbol.replace("ETH", "-ETH")
                        else:
                            exchange_symbol = symbol
                    elif exchange_name == 'bitget':
                        exchange_symbol = symbol.replace("/", "") if "/" in symbol else symbol
                    else:  # mexc and others
                        exchange_symbol = symbol.replace("/", "") if "/" in symbol else symbol
                    
                    # Fetch order book for top of book data (spot market only)
                    # Each exchange has different requirements
                    if exchange_name == 'bitget':
                        # Bitget: uppercase symbol, no 'type' param
                        exchange_symbol = exchange_symbol.upper()
                        order_book = exchange.fetch_order_book(exchange_symbol, limit=5)
                    elif exchange_name == 'kucoin':
                        # KuCoin: dash format, no 'type' param, may need markets loaded
                        # Note: KuCoin may block US IPs (Render servers), handle gracefully
                        try:
                            if not hasattr(exchange, 'markets') or not exchange.markets:
                                exchange.load_markets()
                            # Try to find symbol in markets (KuCoin might have specific format)
                            if exchange_symbol in exchange.markets:
                                order_book = exchange.fetch_order_book(exchange_symbol, limit=5)
                            else:
                                # Try uppercase version
                                exchange_symbol_upper = exchange_symbol.upper()
                                if exchange_symbol_upper in exchange.markets:
                                    order_book = exchange.fetch_order_book(exchange_symbol_upper, limit=5)
                                else:
                                    # Fallback: try direct call
                                    order_book = exchange.fetch_order_book(exchange_symbol, limit=5)
                        except Exception as load_error:
                            error_str = str(load_error)
                            # Check if it's a geographic restriction
                            if "U.S." in error_str or "400302" in error_str or "restricted" in error_str.lower():
                                logger.warning(f"KuCoin blocked due to geographic restriction (Render server IP). Skipping KuCoin.")
                                continue  # Skip KuCoin, continue with other exchanges
                            logger.warning(f"KuCoin market load failed, trying direct: {load_error}")
                            try:
                                order_book = exchange.fetch_order_book(exchange_symbol, limit=5)
                            except Exception as direct_error:
                                error_str = str(direct_error)
                                if "U.S." in error_str or "400302" in error_str or "restricted" in error_str.lower():
                                    logger.warning(f"KuCoin blocked due to geographic restriction. Skipping.")
                                    continue
                                raise
                    elif exchange_name == 'gateio':
                        # Gate.io: slash format, needs 'type': 'spot' param, may need markets loaded
                        try:
                            if not hasattr(exchange, 'markets') or not exchange.markets:
                                exchange.load_markets()
                            # Try to find symbol in markets
                            if exchange_symbol in exchange.markets:
                                order_book = exchange.fetch_order_book(exchange_symbol, limit=5, params={'type': 'spot'})
                            else:
                                # Fallback: try direct call
                                order_book = exchange.fetch_order_book(exchange_symbol, limit=5, params={'type': 'spot'})
                        except Exception as load_error:
                            logger.warning(f"Gate.io market load failed, trying direct: {load_error}")
                            order_book = exchange.fetch_order_book(exchange_symbol, limit=5, params={'type': 'spot'})
                    else:  # mexc and others
                        order_book = exchange.fetch_order_book(exchange_symbol, params={'type': 'spot'})
                    bids = order_book.get('bids', [])
                    asks = order_book.get('asks', [])
                    
                    if bids and asks:
                        # Top of book: first bid and ask
                        bid_price, bid_quantity = bids[0]  # [price, quantity]
                        ask_price, ask_quantity = asks[0]  # [price, quantity]
                        
                        if bid_price > 0 and ask_price > 0 and bid_quantity > 0 and ask_quantity > 0:
                            spread = ask_price - bid_price
                            spread_bps = (spread / bid_price) * 10000 if bid_price > 0 else 0
                            
                            prices.append(PriceData(
                                symbol=symbol,
                                venue=exchange_name,
                                bid_price=bid_price,
                                ask_price=ask_price,
                                bid_quantity=bid_quantity,
                                ask_quantity=ask_quantity,
                                spread_bps=spread_bps,
                                effective_bid=bid_price,
                                effective_ask=ask_price,
                                timestamp=datetime.utcnow()
                            ))
                except Exception as e:
                    logger.warning(f"Failed to get prices from {exchange_name} for symbol {symbol} (converted: {exchange_symbol}): {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    continue
        
        return prices
        
    except Exception as e:
        logger.error(f"Failed to get prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/depth/{symbol}")
async def get_order_book_depth(symbol: str, bps: int = 20):
    """Get order book depth within specified bps for all venues"""
    try:
        sor = await get_sor()
        depth_data = []
        
        # Convert symbol format for exchanges
        if "/" in symbol:
            gateio_symbol = symbol
            mexc_symbol = symbol.replace("/", "")
            bitget_symbol = symbol.replace("/", "")
            kucoin_symbol = symbol.replace("/", "-")
        elif symbol.endswith("USDT"):
            gateio_symbol = symbol.replace("USDT", "/USDT")
            mexc_symbol = symbol
            bitget_symbol = symbol
            kucoin_symbol = symbol.replace("USDT", "-USDT")
        elif symbol.endswith("BTC"):
            gateio_symbol = symbol.replace("BTC", "/BTC")
            mexc_symbol = symbol
            bitget_symbol = symbol
            kucoin_symbol = symbol.replace("BTC", "-BTC")
        elif symbol.endswith("ETH"):
            gateio_symbol = symbol.replace("ETH", "/ETH")
            mexc_symbol = symbol
            bitget_symbol = symbol
            kucoin_symbol = symbol.replace("ETH", "-ETH")
        else:
            gateio_symbol = symbol
            mexc_symbol = symbol
            bitget_symbol = symbol
            kucoin_symbol = symbol
        
        for exchange_name, exchange in sor.exchanges.items():
            try:
                # Get symbol format for this exchange
                if exchange_name == 'gateio':
                    exchange_symbol = gateio_symbol
                elif exchange_name == 'kucoin':
                    exchange_symbol = kucoin_symbol
                elif exchange_name == 'bitget':
                    exchange_symbol = bitget_symbol
                else:  # mexc and others
                    exchange_symbol = mexc_symbol
                
                # Fetch order book with exchange-specific parameters
                if exchange_name == 'bitget':
                    # Bitget: uppercase symbol, no 'type' param
                    exchange_symbol = exchange_symbol.upper()
                    order_book = exchange.fetch_order_book(exchange_symbol, limit=25)
                elif exchange_name == 'kucoin':
                    # KuCoin: dash format, no 'type' param, may need markets loaded
                    # Note: KuCoin may block US IPs (Render servers), handle gracefully
                    try:
                        if not hasattr(exchange, 'markets') or not exchange.markets:
                            exchange.load_markets()
                        # Try to find symbol in markets
                        if exchange_symbol in exchange.markets:
                            order_book = exchange.fetch_order_book(exchange_symbol, limit=25)
                        else:
                            # Try uppercase version
                            exchange_symbol_upper = exchange_symbol.upper()
                            if exchange_symbol_upper in exchange.markets:
                                order_book = exchange.fetch_order_book(exchange_symbol_upper, limit=25)
                            else:
                                # Fallback: try direct call
                                order_book = exchange.fetch_order_book(exchange_symbol, limit=25)
                    except Exception as load_error:
                        error_str = str(load_error)
                        # Check if it's a geographic restriction
                        if "U.S." in error_str or "400302" in error_str or "restricted" in error_str.lower():
                            logger.warning(f"KuCoin blocked due to geographic restriction (Render server IP). Skipping KuCoin.")
                            continue  # Skip KuCoin, continue with other exchanges
                        logger.warning(f"KuCoin market load failed, trying direct: {load_error}")
                        try:
                            order_book = exchange.fetch_order_book(exchange_symbol, limit=25)
                        except Exception as direct_error:
                            error_str = str(direct_error)
                            if "U.S." in error_str or "400302" in error_str or "restricted" in error_str.lower():
                                logger.warning(f"KuCoin blocked due to geographic restriction. Skipping.")
                                continue
                            raise
                elif exchange_name == 'gateio':
                    # Gate.io: slash format, needs 'type': 'spot' param, may need markets loaded
                    try:
                        if not hasattr(exchange, 'markets') or not exchange.markets:
                            exchange.load_markets()
                        # Try to find symbol in markets
                        if exchange_symbol in exchange.markets:
                            order_book = exchange.fetch_order_book(exchange_symbol, limit=25, params={'type': 'spot'})
                        else:
                            # Fallback: try direct call
                            order_book = exchange.fetch_order_book(exchange_symbol, limit=25, params={'type': 'spot'})
                    except Exception as load_error:
                        logger.warning(f"Gate.io market load failed, trying direct: {load_error}")
                        order_book = exchange.fetch_order_book(exchange_symbol, limit=25, params={'type': 'spot'})
                else:  # mexc and others
                    order_book = exchange.fetch_order_book(exchange_symbol, params={'type': 'spot'})
                bids = order_book.get('bids', [])
                asks = order_book.get('asks', [])
                
                if not bids or not asks:
                    continue
                
                # Calculate depth for both sides
                for side in ['buy', 'sell']:
                    if side == 'buy':
                        orders = asks  # Buy at ask prices
                        base_price = asks[0][0] if asks else 0
                    else:
                        orders = bids  # Sell at bid prices  
                        base_price = bids[0][0] if bids else 0
                    
                    if base_price == 0:
                        continue
                    
                    # Calculate price range within bps
                    price_range = base_price * (bps / 10000)
                    if side == 'buy':
                        max_price = base_price + price_range
                    else:
                        max_price = base_price - price_range
                    
                    # Scan orders within price range
                    total_qty = 0
                    total_value = 0
                    
                    for price, quantity in orders:
                        if side == 'buy' and price <= max_price:
                            total_qty += quantity
                            total_value += price * quantity
                        elif side == 'sell' and price >= max_price:
                            total_qty += quantity
                            total_value += price * quantity
                        else:
                            break  # Orders are sorted, so we can stop
                    
                    if total_qty > 0:
                        vwap = total_value / total_qty
                        depth_data.append({
                            'venue': exchange_name,
                            'side': side,
                            'symbol': symbol,
                            'base_price': base_price,
                            'max_price': max_price,
                            'total_quantity': total_qty,
                            'vwap': vwap,
                            'bps': bps
                        })
                        
            except Exception as e:
                logger.warning(f"Failed to get depth from {exchange_name}: {e}")
                continue
        
        return depth_data
        
    except Exception as e:
        logger.error(f"Failed to get order book depth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/arbitrage/{symbol}", response_model=List[ArbitrageOpportunity])
async def get_arbitrage_opportunities(
    symbol: str,
    min_spread: float = Query(0.001, ge=0)
):
    """Get arbitrage opportunities for a symbol"""
    try:
        sor = await get_sor()
        opportunities = await sor.get_arbitrage_opportunities(symbol, min_spread)
        
        arb_opportunities = []
        for opp in opportunities:
            arb_opportunities.append(ArbitrageOpportunity(
                symbol=symbol,
                buy_venue=opp.get("buy_venue", ""),
                sell_venue=opp.get("sell_venue", ""),
                buy_price=float(opp.get("buy_price", 0)),
                sell_price=float(opp.get("sell_price", 0)),
                spread_bps=float(opp.get("spread_bps", 0)),
                potential_profit=float(opp.get("potential_profit", 0)),
                timestamp=datetime.utcnow()
            ))
        
        return arb_opportunities
        
    except Exception as e:
        logger.error(f"Failed to get arbitrage opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Risk management endpoints
@app.get("/risk/{user_id}", response_model=RiskMetrics)
async def get_risk_metrics(
    user_id: str,
    symbol: Optional[str] = Query(None),
    db = Depends(get_db)
):
    """Get risk metrics for a user"""
    try:
        sor = await get_sor()
        risk_summary = await sor.get_risk_summary()
        
        # Get user-specific risk data from database
        where_clause = "user_id = :user_id"
        params = {"user_id": user_id}
        
        if symbol:
            where_clause += " AND symbol = :symbol"
            params["symbol"] = symbol
        
        result = db.execute(text(f"""
            SELECT user_id, symbol, total_exposure, daily_volume, position_size,
                   unrealized_pnl, realized_pnl, max_drawdown, timestamp
            FROM risk_metrics
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT 1
        """), params).fetchone()
        
        if not result:
            # Return default values if no data found
            return RiskMetrics(
                user_id=user_id,
                symbol=symbol,
                total_exposure=0.0,
                daily_volume=0.0,
                position_size=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                max_drawdown=0.0,
                timestamp=datetime.utcnow()
            )
        
        return RiskMetrics(
            user_id=result.user_id,
            symbol=result.symbol,
            total_exposure=float(result.total_exposure),
            daily_volume=float(result.daily_volume),
            position_size=float(result.position_size),
            unrealized_pnl=float(result.unrealized_pnl),
            realized_pnl=float(result.realized_pnl),
            max_drawdown=float(result.max_drawdown),
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System endpoints
@app.get("/system/health", response_model=SystemHealth)
async def get_system_health():
    """Get system health and performance metrics"""
    try:
        sor = await get_sor()
        stats = await sor.get_statistics()
        
        return SystemHealth(
            status="healthy",
            uptime=stats.get("uptime", 0),
            active_venues=len(stats.get("venues", {})),
            total_orders=stats.get("total_orders", 0),
            success_rate=stats.get("success_rate", 0),
            average_execution_time=stats.get("average_execution_time", 0),
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/stats", response_model=Dict[str, Any])
async def get_system_stats():
    """Get detailed system statistics"""
    try:
        sor = await get_sor()
        return await sor.get_statistics()
        
    except Exception as e:
        logger.error(f"Failed to get system stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
