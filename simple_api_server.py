"""
Simple API Server for Smart Order Router
No authentication required for testing
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import our SmartOrderRouter
from smart_order_router import SmartOrderRouter
from models import OrderSide, OrderType, ExecutionResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
@app.get("/health")
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
            # Create a single price entry with the best bid/ask
            prices.append(PriceData(
                symbol=symbol,
                venue="best",
                bid_price=price_data.get("best_bid", 0),
                ask_price=price_data.get("best_ask", 0),
                bid_quantity=1000.0,  # Default quantity
                ask_quantity=1000.0,  # Default quantity
                spread_bps=price_data.get("spread_bps", 0),
                effective_bid=price_data.get("best_bid", 0),
                effective_ask=price_data.get("best_ask", 0),
                timestamp=datetime.utcnow()
            ))
        
        return prices
        
    except Exception as e:
        logger.error(f"Failed to get prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Order endpoints
@app.post("/orders", response_model=OrderResponse)
async def create_order(order_request: OrderRequest):
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
        logger.error(f"Failed to create order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System endpoints
@app.get("/system/stats")
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
        "simple_api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
