"""
Data models for Smart Order Router
"""

from enum import Enum
from decimal import Decimal
from typing import List, Dict, Any, Optional
from datetime import datetime


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExecutionResult:
    """Result of order execution"""
    
    def __init__(
        self,
        success: bool = False,
        order_id: str = None,
        total_filled: Decimal = Decimal("0"),
        average_price: Decimal = None,
        total_cost: Decimal = Decimal("0"),
        executions: List[Dict[str, Any]] = None,
        error_message: str = None
    ):
        self.success = success
        self.order_id = order_id or f"order-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self.total_filled = total_filled
        self.average_price = average_price
        self.total_cost = total_cost
        self.executions = executions or []
        self.error_message = error_message


class Order:
    """Order model"""
    
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal = None,
        user_id: str = None,
        max_slippage: Decimal = None
    ):
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.user_id = user_id
        self.max_slippage = max_slippage
        self.status = OrderStatus.PENDING
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.total_filled = Decimal("0")
        self.average_price = None
        self.total_cost = Decimal("0")
        self.executions = []


class PriceData:
    """Price data model"""
    
    def __init__(
        self,
        symbol: str,
        venue: str,
        bid_price: Decimal,
        ask_price: Decimal,
        bid_quantity: Decimal,
        ask_quantity: Decimal,
        timestamp: datetime = None
    ):
        self.symbol = symbol
        self.venue = venue
        self.bid_price = bid_price
        self.ask_price = ask_price
        self.bid_quantity = bid_quantity
        self.ask_quantity = ask_quantity
        self.timestamp = timestamp or datetime.utcnow()
        self.spread = ask_price - bid_price
        self.spread_bps = (self.spread / bid_price * 10000) if bid_price > 0 else 0


class ArbitrageOpportunity:
    """Arbitrage opportunity model"""
    
    def __init__(
        self,
        symbol: str,
        buy_venue: str,
        sell_venue: str,
        buy_price: Decimal,
        sell_price: Decimal,
        quantity: Decimal,
        potential_profit: Decimal
    ):
        self.symbol = symbol
        self.buy_venue = buy_venue
        self.sell_venue = sell_venue
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.quantity = quantity
        self.potential_profit = potential_profit
        self.spread = sell_price - buy_price
        self.spread_bps = (self.spread / buy_price * 10000) if buy_price > 0 else 0
        self.timestamp = datetime.utcnow()


class RiskMetrics:
    """Risk metrics model"""
    
    def __init__(
        self,
        user_id: str = None,
        symbol: str = None,
        total_exposure: Decimal = Decimal("0"),
        daily_volume: Decimal = Decimal("0"),
        position_size: Decimal = Decimal("0"),
        unrealized_pnl: Decimal = Decimal("0"),
        realized_pnl: Decimal = Decimal("0"),
        max_drawdown: Decimal = Decimal("0")
    ):
        self.user_id = user_id
        self.symbol = symbol
        self.total_exposure = total_exposure
        self.daily_volume = daily_volume
        self.position_size = position_size
        self.unrealized_pnl = unrealized_pnl
        self.realized_pnl = realized_pnl
        self.max_drawdown = max_drawdown
        self.timestamp = datetime.utcnow()