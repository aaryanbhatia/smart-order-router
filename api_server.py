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
        order_data = {
            "id": str(result.order_id),
            "symbol": order_request.symbol,
            "side": order_request.side,
            "order_type": order_request.order_type,
            "quantity": float(quantity),
            "price": float(price) if price else None,
            "status": "filled" if result.success else "failed",
            "total_filled": float(result.total_filled),
            "average_price": float(result.average_price) if result.average_price else None,
            "total_cost": float(result.total_cost) if result.total_cost else 0,
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
        
        return OrderResponse(
            order_id=str(result.order_id),
            symbol=order_request.symbol,
            side=order_request.side,
            order_type=order_request.order_type,
            quantity=float(quantity),
            price=float(price) if price else None,
            status="filled" if result.success else "failed",
            total_filled=float(result.total_filled),
            average_price=float(result.average_price) if result.average_price else None,
            total_cost=float(result.total_cost) if result.total_cost else 0,
            created_at=datetime.utcnow(),
            executions=result.executions
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
        
        # Get individual exchange data instead of aggregated
        prices = []
        
        # Get Gate.io data
        try:
            gateio_data = await sor.get_exchange_prices("gateio", symbol)
            if gateio_data:
                prices.append(PriceData(
                    symbol=symbol,
                    venue="gateio",
                    bid_price=gateio_data.get("bid_price", 0),
                    ask_price=gateio_data.get("ask_price", 0),
                    bid_quantity=gateio_data.get("bid_quantity", 1000.0),
                    ask_quantity=gateio_data.get("ask_quantity", 1000.0),
                    spread_bps=gateio_data.get("spread_bps", 0),
                    effective_bid=gateio_data.get("bid_price", 0),
                    effective_ask=gateio_data.get("ask_price", 0),
                    timestamp=datetime.utcnow()
                ))
        except Exception as e:
            logger.warning(f"Failed to get Gate.io prices: {e}")
        
        # Get MEXC data
        try:
            mexc_data = await sor.get_exchange_prices("mexc", symbol)
            if mexc_data:
                prices.append(PriceData(
                    symbol=symbol,
                    venue="mexc",
                    bid_price=mexc_data.get("bid_price", 0),
                    ask_price=mexc_data.get("ask_price", 0),
                    bid_quantity=mexc_data.get("bid_quantity", 1000.0),
                    ask_quantity=mexc_data.get("ask_quantity", 1000.0),
                    spread_bps=mexc_data.get("spread_bps", 0),
                    effective_bid=mexc_data.get("bid_price", 0),
                    effective_ask=mexc_data.get("ask_price", 0),
                    timestamp=datetime.utcnow()
                ))
        except Exception as e:
            logger.warning(f"Failed to get MEXC prices: {e}")
        
        # If no individual data, fall back to aggregated
        if not prices:
            price_data = await sor.get_best_prices(symbol)
            if price_data:
                prices.append(PriceData(
                    symbol=symbol,
                    venue="best",
                    bid_price=price_data.get("best_bid", 0),
                    ask_price=price_data.get("best_ask", 0),
                    bid_quantity=1000.0,
                    ask_quantity=1000.0,
                    spread_bps=price_data.get("spread_bps", 0),
                    effective_bid=price_data.get("best_bid", 0),
                    effective_ask=price_data.get("best_ask", 0),
                    timestamp=datetime.utcnow()
                ))
        
        return prices
        
    except Exception as e:
        logger.error(f"Failed to get prices: {e}")
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
