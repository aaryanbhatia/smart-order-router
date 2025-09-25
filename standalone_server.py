#!/usr/bin/env python3
"""
Standalone server for Render deployment
No external dependencies on config module
"""

import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn

# Create FastAPI app
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

# Pydantic models
class OrderRequest(BaseModel):
    symbol: str
    side: str
    order_type: str
    quantity: float
    price: Optional[float] = None
    max_slippage: Optional[float] = None
    user_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: str
    timestamp: str

# Health check endpoint
@app.get("/", response_model=HealthResponse)
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    import datetime
    return HealthResponse(
        status="healthy",
        message="SOR API is running",
        timestamp=datetime.datetime.utcnow().isoformat()
    )

# Basic order endpoint (simplified)
@app.post("/orders")
async def create_order(order_request: OrderRequest):
    """Create a new order (simplified version)"""
    return {
        "order_id": "test-order-123",
        "symbol": order_request.symbol,
        "side": order_request.side,
        "order_type": order_request.order_type,
        "quantity": order_request.quantity,
        "status": "pending",
        "message": "Order received (demo mode - no actual trading)",
        "note": "This is a simplified version for deployment testing"
    }

# Price endpoint (simplified)
@app.get("/prices/{symbol}")
async def get_prices(symbol: str):
    """Get current prices for a symbol (simplified)"""
    return {
        "symbol": symbol,
        "prices": {
            "bid": 50000.0,
            "ask": 50001.0,
            "spread": 1.0
        },
        "message": "Demo prices - not real market data"
    }

# System info endpoint
@app.get("/system/info")
async def get_system_info():
    """Get system information"""
    return {
        "status": "running",
        "version": "1.0.0",
        "environment": "cloud",
        "message": "SOR API is running in cloud deployment"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting standalone SOR server on port {port}")
    print(f"🌐 Health check: http://0.0.0.0:{port}/health")
    print(f"📚 API docs: http://0.0.0.0:{port}/docs")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
