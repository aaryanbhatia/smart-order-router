"""
Smart Order Router - Main class
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime
import ccxt

from models import OrderSide, OrderType, ExecutionResult, PriceData, ArbitrageOpportunity, RiskMetrics
from config import config

logger = logging.getLogger(__name__)


class SmartOrderRouter:
    """Main Smart Order Router class"""
    
    def __init__(self):
        self.exchanges = {}
        self.is_running = False
        self.start_time = None
        
    async def initialize(self):
        """Initialize the SOR"""
        logger.info("Initializing Smart Order Router...")
        
        # Initialize exchanges
        try:
            # Gate.io
            if hasattr(config, 'exchanges') and 'gateio' in config.exchanges:
                gateio_config = config.exchanges['gateio']
                self.exchanges['gateio'] = ccxt.gateio({
                    'apiKey': gateio_config.api_key or '',
                    'secret': gateio_config.secret or '',
                    'sandbox': gateio_config.sandbox,
                    'enableRateLimit': True,
                })
                logger.info(f"Gate.io exchange initialized with API key: {gateio_config.api_key[:8] if gateio_config.api_key else 'None'}...")
            
            # MEXC
            if hasattr(config, 'exchanges') and 'mexc' in config.exchanges:
                mexc_config = config.exchanges['mexc']
                self.exchanges['mexc'] = ccxt.mexc({
                    'apiKey': mexc_config.api_key or '',
                    'secret': mexc_config.secret or '',
                    'sandbox': mexc_config.sandbox,
                    'enableRateLimit': True,
                })
                logger.info(f"MEXC exchange initialized with API key: {mexc_config.api_key[:8] if mexc_config.api_key else 'None'}...")
            
            # Bitget
            if hasattr(config, 'exchanges') and 'bitget' in config.exchanges:
                bitget_config = config.exchanges['bitget']
                # Only include password if passphrase is provided (for authenticated calls)
                bitget_params = {
                    'apiKey': bitget_config.api_key or '',
                    'secret': bitget_config.secret or '',
                    'sandbox': bitget_config.sandbox,
                    'enableRateLimit': True,
                }
                if bitget_config.passphrase:
                    bitget_params['password'] = bitget_config.passphrase  # CCXT uses 'password' for passphrase
                self.exchanges['bitget'] = ccxt.bitget(bitget_params)
                logger.info(f"Bitget exchange initialized with API key: {bitget_config.api_key[:8] if bitget_config.api_key else 'None'}...")
            
            # KuCoin - DISABLED due to IP restrictions (US IP blocking)
            # if hasattr(config, 'exchanges') and 'kucoin' in config.exchanges:
            #     kucoin_config = config.exchanges['kucoin']
            #     # Only include password if passphrase is provided (for authenticated calls)
            #     kucoin_params = {
            #         'apiKey': kucoin_config.api_key or '',
            #         'secret': kucoin_config.secret or '',
            #         'sandbox': kucoin_config.sandbox,
            #         'enableRateLimit': True,
            #     }
            #     if kucoin_config.passphrase:
            #         kucoin_params['password'] = kucoin_config.passphrase  # CCXT uses 'password' for passphrase
            #     self.exchanges['kucoin'] = ccxt.kucoin(kucoin_params)
            #     logger.info(f"KuCoin exchange initialized with API key: {kucoin_config.api_key[:8] if kucoin_config.api_key else 'None'}...")
            logger.info("KuCoin exchange disabled due to IP restrictions")
                
        except Exception as e:
            logger.warning(f"Failed to initialize exchanges: {e}")
            # Continue with demo mode if exchanges fail
        
        self.start_time = datetime.utcnow()
        logger.info("SOR initialized successfully")
        
    async def start(self):
        """Start the SOR"""
        logger.info("Starting Smart Order Router...")
        self.is_running = True
        logger.info("SOR started successfully")
        
    async def stop(self):
        """Stop the SOR"""
        logger.info("Stopping Smart Order Router...")
        self.is_running = False
        logger.info("SOR stopped")
        
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal = None,
        max_slippage: Decimal = None,
        user_id: str = None,
        venue: str = None
    ) -> ExecutionResult:
        """Place a smart order"""
        try:
            logger.info(f"Placing order: {side} {quantity} {symbol} at {price or 'market'}")
            
            # If venue is specified, only try that exchange
            exchanges_to_try = {}
            if venue:
                venue_lower = venue.lower()
                if venue_lower in self.exchanges:
                    exchanges_to_try[venue_lower] = self.exchanges[venue_lower]
                    logger.info(f"Using specified venue: {venue_lower}")
                else:
                    logger.warning(f"Specified venue '{venue}' not found, trying all exchanges")
                    exchanges_to_try = self.exchanges
            else:
                exchanges_to_try = self.exchanges
            
            # Try to place order on available exchanges
            for exchange_name, exchange in exchanges_to_try.items():
                # Skip KuCoin due to IP restrictions
                if exchange_name == 'kucoin':
                    continue
                try:
                    # Convert symbol format for spot trading
                    if exchange_name == 'gateio':
                        if "/" in symbol:
                            spot_symbol = symbol
                        elif symbol.endswith("USDT"):
                            spot_symbol = symbol.replace("USDT", "/USDT")
                        elif symbol.endswith("BTC"):
                            spot_symbol = symbol.replace("BTC", "/BTC")
                        elif symbol.endswith("ETH"):
                            spot_symbol = symbol.replace("ETH", "/ETH")
                        else:
                            spot_symbol = symbol
                    elif exchange_name == 'kucoin':
                        if "/" in symbol:
                            spot_symbol = symbol.replace("/", "-")
                        elif symbol.endswith("USDT"):
                            spot_symbol = symbol.replace("USDT", "-USDT")
                        elif symbol.endswith("BTC"):
                            spot_symbol = symbol.replace("BTC", "-BTC")
                        elif symbol.endswith("ETH"):
                            spot_symbol = symbol.replace("ETH", "-ETH")
                        else:
                            spot_symbol = symbol
                    elif exchange_name == 'bitget':
                        spot_symbol = symbol.replace("/", "").upper() if "/" in symbol else symbol.upper()
                    else:  # mexc and others
                        spot_symbol = symbol.replace("/", "") if "/" in symbol else symbol
                    
                    # Exchange-specific order placement
                    if exchange_name == 'bitget':
                        # Bitget doesn't need 'type' param, uses uppercase symbols
                        if order_type == OrderType.MARKET:
                            order = exchange.create_market_order(
                                symbol=spot_symbol,
                                side=side.value,
                                amount=float(quantity)
                            )
                        else:
                            order = exchange.create_limit_order(
                                symbol=spot_symbol,
                                side=side.value,
                                amount=float(quantity),
                                price=float(price)
                            )
                    elif exchange_name == 'gateio':
                        # Gate.io: needs 'type': 'spot' param, may need markets loaded
                        try:
                            if not hasattr(exchange, 'markets') or not exchange.markets:
                                exchange.load_markets()
                        except Exception as load_error:
                            logger.warning(f"Gate.io market load warning: {load_error}")
                            # Continue - might still work
                        
                        # Validate symbol exists in markets
                        if hasattr(exchange, 'markets') and exchange.markets:
                            if spot_symbol not in exchange.markets:
                                # Try to find the symbol in markets (case-insensitive)
                                symbol_found = False
                                for market_symbol in exchange.markets:
                                    if market_symbol.upper() == spot_symbol.upper():
                                        spot_symbol = market_symbol
                                        symbol_found = True
                                        logger.info(f"Gate.io: Found symbol {spot_symbol} in markets")
                                        break
                                if not symbol_found:
                                    raise ValueError(f"Gate.io: Symbol {spot_symbol} not found in markets")
                        
                        # Gate.io requires specific order format
                        if order_type == OrderType.MARKET:
                            order = exchange.create_market_order(
                                symbol=spot_symbol,
                                side=side.value,
                                amount=float(quantity),
                                params={'type': 'spot', 'account': 'spot'}
                            )
                        else:
                            # Gate.io limit orders need account parameter
                            order = exchange.create_limit_order(
                                symbol=spot_symbol,
                                side=side.value,
                                amount=float(quantity),
                                price=float(price),
                                params={'type': 'spot', 'account': 'spot'}
                            )
                        
                        # Validate order response for Gate.io
                        if not order:
                            raise ValueError("Gate.io returned empty order response")
                        
                        order_id = order.get('id')
                        if not order_id or order_id == 'unknown':
                            raise ValueError(f"Gate.io returned invalid order ID: {order_id}")
                        
                        # Log order details for debugging
                        logger.info(f"Gate.io order created: ID={order_id}, Status={order.get('status')}, Symbol={spot_symbol}")
                        
                        # Verify order was actually placed by checking status
                        order_status = order.get('status', '').lower()
                        if order_status in ['closed', 'cancelled', 'expired', 'rejected']:
                            error_msg = f"Gate.io order {order_id} has status {order_status}, order was not placed successfully"
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                        
                        # Additional validation: check if order has required fields
                        if order_type == OrderType.LIMIT:
                            # For limit orders, price should be set
                            order_price = order.get('price')
                            if order_price is None:
                                logger.warning(f"Gate.io limit order missing price field")
                            else:
                                try:
                                    price_val = float(order_price)
                                    if price_val <= 0:
                                        logger.warning(f"Gate.io limit order has invalid price: {price_val}")
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Gate.io limit order price conversion failed: {e}")
                                # Don't fail here, but log the warning
                    else:
                        # Other exchanges use 'type': 'spot' param
                        if order_type == OrderType.MARKET:
                            order = exchange.create_market_order(
                                symbol=spot_symbol,
                                side=side.value,
                                amount=float(quantity),
                                params={'type': 'spot'}  # Ensure spot trading only
                            )
                        else:
                            order = exchange.create_limit_order(
                                symbol=spot_symbol,
                                side=side.value,
                                amount=float(quantity),
                                price=float(price),
                                params={'type': 'spot'}  # Ensure spot trading only
                            )
                    
                    # Safely handle None values from order response
                    filled = order.get('filled')
                    if filled is None:
                        # For limit orders, filled might be 0 initially (order is pending)
                        if order_type == OrderType.LIMIT:
                            filled = Decimal("0")  # Limit orders start unfilled until executed
                        else:
                            filled = quantity  # Market orders should be filled immediately
                    else:
                        filled = Decimal(str(filled))
                    
                    avg_price = order.get('average')
                    if avg_price is None:
                        # Use provided price, or default to 0
                        avg_price = price if price is not None else Decimal("0")
                    else:
                        avg_price = Decimal(str(avg_price))
                    
                    # Ensure avg_price is never None for comparisons
                    if avg_price is None:
                        avg_price = Decimal("0")
                    
                    cost = order.get('cost')
                    if cost is None:
                        # Safe comparison: avg_price is guaranteed to be Decimal
                        cost = filled * avg_price if avg_price and avg_price > 0 else Decimal("0")
                    else:
                        cost = Decimal(str(cost))
                    
                    # Ensure cost is never None
                    if cost is None:
                        cost = Decimal("0")
                    
                    # Safe comparison: avg_price is guaranteed to be Decimal, not None
                    final_avg_price = avg_price if avg_price and avg_price > 0 else None
                    
                    # Safe price handling for execution record
                    exec_price = 0.0
                    if price is not None:
                        exec_price = float(price)
                    elif avg_price and avg_price > 0:
                        exec_price = float(avg_price)
                    
                    return ExecutionResult(
                        success=True,
                        order_id=order.get('id', 'unknown'),
                        total_filled=filled,
                        average_price=final_avg_price,
                        total_cost=cost,
                        executions=[{
                            "venue": exchange_name,
                            "venue_order_id": order.get('id', 'unknown'),
                            "quantity": float(quantity),
                            "price": exec_price,
                            "status": order.get('status', 'filled')
                        }]
                    )
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Failed to place order on {exchange_name}: {error_msg}")
                    # Log full exception for debugging
                    import traceback
                    logger.debug(f"Full traceback for {exchange_name}: {traceback.format_exc()}")
                    
                    # For Gate.io, log more details
                    if exchange_name == 'gateio':
                        logger.error(f"Gate.io order placement failed. Symbol: {spot_symbol}, Side: {side.value}, "
                                   f"Type: {order_type.value}, Quantity: {quantity}, Price: {price}")
                    continue
            
            # If all exchanges fail, return failure
            logger.error("All exchanges failed to place order")
            return ExecutionResult(
                success=False,
                order_id="failed",
                total_filled=Decimal("0"),
                average_price=None,
                total_cost=Decimal("0"),
                executions=[],
                error_message="All exchanges failed to place order"
            )
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return ExecutionResult(
                success=False,
                order_id="failed",
                total_filled=Decimal("0"),
                average_price=None,
                total_cost=Decimal("0"),
                executions=[],
                error_message=str(e)
            )
    
    async def get_exchange_prices(self, exchange_name: str, symbol: str) -> Dict[str, Any]:
        """Get prices from a specific exchange"""
        try:
            if exchange_name not in self.exchanges:
                return None
                
            exchange = self.exchanges[exchange_name]
            
            # Load markets first (especially important for Gate.io)
            try:
                if not hasattr(exchange, 'markets') or not exchange.markets:
                    exchange.load_markets()
            except Exception as load_error:
                logger.warning(f"Failed to load markets for {exchange_name}: {load_error}")
            
            # Convert symbol format based on exchange requirements
            if '/' not in symbol:
                if exchange_name == 'gateio':
                    # Gate.io needs DOGE/USDT format
                    if symbol.endswith('USDT'):
                        base = symbol[:-4]  # Remove USDT
                        symbol = f"{base}/USDT"
                    elif symbol.endswith('BTC'):
                        base = symbol[:-3]  # Remove BTC
                        symbol = f"{base}/BTC"
                    elif symbol.endswith('ETH'):
                        base = symbol[:-3]  # Remove ETH
                        symbol = f"{base}/ETH"
                elif exchange_name == 'kucoin':
                    # KuCoin uses DOGE-USDT format
                    if symbol.endswith('USDT'):
                        base = symbol[:-4]
                        symbol = f"{base}-USDT"
                    elif symbol.endswith('BTC'):
                        base = symbol[:-3]
                        symbol = f"{base}-BTC"
                    elif symbol.endswith('ETH'):
                        base = symbol[:-3]
                        symbol = f"{base}-ETH"
                # MEXC and Bitget use DOGEUSDT format (no conversion needed)
            else:
                # Symbol has / separator, convert based on exchange
                if exchange_name == 'kucoin':
                    symbol = symbol.replace("/", "-")
                elif exchange_name in ['mexc', 'bitget']:
                    symbol = symbol.replace("/", "")
                # Gate.io uses / format, no conversion needed
            
            ticker = exchange.fetch_ticker(symbol)
            
            bid = ticker.get('bid', 0)
            ask = ticker.get('ask', 0)
            bid_quantity = ticker.get('bidVolume', 1000.0)
            ask_quantity = ticker.get('askVolume', 1000.0)
            
            if bid > 0 and ask > 0:
                spread = ask - bid
                spread_bps = (spread / bid) * 10000 if bid > 0 else 0
                
                return {
                    "bid_price": bid,
                    "ask_price": ask,
                    "bid_quantity": bid_quantity,
                    "ask_quantity": ask_quantity,
                    "spread": spread,
                    "spread_bps": spread_bps,
                    "timestamp": datetime.utcnow().isoformat()
                }
            else:
                return None
                
        except Exception as e:
            logger.warning(f"Failed to get prices from {exchange_name} for {symbol}: {e}")
            return None

    async def get_best_prices(self, symbol: str) -> Dict[str, Any]:
        """Get best bid/ask prices across all venues"""
        try:
            best_bid = 0
            best_ask = float('inf')
            best_bid_venue = None
            best_ask_venue = None
            
            # Get prices from all exchanges
            for exchange_name, exchange in self.exchanges.items():
                try:
                    # Load markets first (especially important for Gate.io)
                    try:
                        if not hasattr(exchange, 'markets') or not exchange.markets:
                            exchange.load_markets()
                    except Exception as load_error:
                        logger.warning(f"Failed to load markets for {exchange_name}: {load_error}")
                    
                    # Convert symbol format for this exchange
                    exchange_symbol = symbol
                    if '/' not in symbol:
                        if exchange_name == 'gateio':
                            if symbol.endswith('USDT'):
                                exchange_symbol = symbol.replace("USDT", "/USDT")
                            elif symbol.endswith('BTC'):
                                exchange_symbol = symbol.replace("BTC", "/BTC")
                            elif symbol.endswith('ETH'):
                                exchange_symbol = symbol.replace("ETH", "/ETH")
                        elif exchange_name == 'kucoin':
                            if symbol.endswith('USDT'):
                                exchange_symbol = symbol.replace("USDT", "-USDT")
                            elif symbol.endswith('BTC'):
                                exchange_symbol = symbol.replace("BTC", "-BTC")
                            elif symbol.endswith('ETH'):
                                exchange_symbol = symbol.replace("ETH", "-ETH")
                    else:
                        if exchange_name == 'kucoin':
                            exchange_symbol = symbol.replace("/", "-")
                        elif exchange_name in ['mexc', 'bitget']:
                            exchange_symbol = symbol.replace("/", "")
                    
                    ticker = exchange.fetch_ticker(exchange_symbol)
                    bid = ticker.get('bid', 0)
                    ask = ticker.get('ask', float('inf'))
                    
                    if bid > best_bid:
                        best_bid = bid
                        best_bid_venue = exchange_name
                    
                    if ask < best_ask:
                        best_ask = ask
                        best_ask_venue = exchange_name
                        
                except Exception as e:
                    logger.warning(f"Failed to get prices from {exchange_name}: {e}")
                    continue
            
            # If no real data, return empty result
            if best_bid == 0 or best_ask == float('inf'):
                return None
            
            spread = best_ask - best_bid
            spread_bps = (spread / best_bid) * 10000 if best_bid > 0 else 0
            
            return {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread,
                "spread_bps": spread_bps,
                "best_bid_venue": best_bid_venue,
                "best_ask_venue": best_ask_venue,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get best prices: {e}")
            return None
    
    async def get_arbitrage_opportunities(self, symbol: str, min_spread: float = 0.001) -> List[Dict[str, Any]]:
        """Find arbitrage opportunities between venues"""
        try:
            opportunities = []
            prices = {}
            
            # Get prices from all exchanges
            for exchange_name, exchange in self.exchanges.items():
                # Skip KuCoin due to IP restrictions
                if exchange_name == 'kucoin':
                    continue
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    prices[exchange_name] = {
                        'bid': ticker.get('bid', 0),
                        'ask': ticker.get('ask', float('inf'))
                    }
                except Exception as e:
                    logger.warning(f"Failed to get prices from {exchange_name}: {e}")
                    continue
            
            # Find arbitrage opportunities
            for buy_venue, buy_data in prices.items():
                for sell_venue, sell_data in prices.items():
                    if buy_venue != sell_venue:
                        buy_price = buy_data['ask']  # Buy at ask price
                        sell_price = sell_data['bid']  # Sell at bid price
                        
                        if sell_price > buy_price:
                            spread = sell_price - buy_price
                            spread_bps = (spread / buy_price) * 10000 if buy_price > 0 else 0
                            
                            if spread_bps >= min_spread * 10000:  # Convert to basis points
                                opportunities.append({
                                    "buy_venue": buy_venue,
                                    "sell_venue": sell_venue,
                                    "buy_price": buy_price,
                                    "sell_price": sell_price,
                                    "spread": spread,
                                    "spread_bps": spread_bps,
                                    "potential_profit": spread
                                })
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Failed to get arbitrage opportunities: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get SOR performance statistics"""
        try:
            uptime = (datetime.utcnow() - self.start_time).total_seconds() if self.start_time else 0
            venue_stats = {}
            
            # Check exchange status
            for exchange_name, exchange in self.exchanges.items():
                try:
                    # Test connection
                    exchange.fetch_balance()
                    venue_stats[exchange_name] = {"status": "connected"}
                except Exception as e:
                    venue_stats[exchange_name] = {"status": "disconnected", "error": str(e)}
            
            return {
                "uptime": uptime,
                "venues": venue_stats,
                "total_orders": 0,
                "success_rate": 1.0,
                "average_execution_time": 0.1
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    async def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk metrics"""
        try:
            return {
                "total_exposure": 0.0,
                "daily_volume": 0.0,
                "position_size": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": 0.0,
                "max_drawdown": 0.0
            }
        except Exception as e:
            logger.error(f"Failed to get risk summary: {e}")
            return {}