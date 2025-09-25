"""
Configuration management for Smart Order Router
"""

import os
from typing import Dict, List, Optional
from enum import Enum


class ExchangeType(str, Enum):
    CEX = "cex"
    DEX = "dex"


class ExchangeConfig:
    """Configuration for individual exchanges"""
    def __init__(self, name: str, type: ExchangeType, **kwargs):
        self.name = name
        self.type = type
        self.api_key = kwargs.get('api_key')
        self.secret = kwargs.get('secret')
        self.passphrase = kwargs.get('passphrase')
        self.sandbox = kwargs.get('sandbox', False)
        self.enabled = kwargs.get('enabled', True)
        self.rate_limit = kwargs.get('rate_limit', 100)
        self.min_order_size = kwargs.get('min_order_size', 0.001)
        self.trading_fee = kwargs.get('trading_fee', 0.001)
        self.withdrawal_fee = kwargs.get('withdrawal_fee', 0.0)


class SORConfig:
    """Main SOR configuration"""
    
    def __init__(self):
        # Supported exchanges
        self.exchanges: Dict[str, ExchangeConfig] = {
            "gateio": ExchangeConfig(
                name="gateio",
                type=ExchangeType.CEX,
                api_key=os.getenv("GATEIO_API_KEY", ""),
                secret=os.getenv("GATEIO_SECRET", ""),
                sandbox=os.getenv("GATEIO_SANDBOX", "true").lower() == "true",
                trading_fee=0.002,
                min_order_size=0.001
            ),
            "kucoin": ExchangeConfig(
                name="kucoin", 
                type=ExchangeType.CEX,
                api_key=os.getenv("KUCOIN_API_KEY", ""),
                secret=os.getenv("KUCOIN_SECRET", ""),
                passphrase=os.getenv("KUCOIN_PASSPHRASE", ""),
                sandbox=os.getenv("KUCOIN_SANDBOX", "true").lower() == "true",
                trading_fee=0.001,
                min_order_size=0.001
            ),
            "bitget": ExchangeConfig(
                name="bitget",
                type=ExchangeType.CEX,
                api_key=os.getenv("BITGET_API_KEY", ""),
                secret=os.getenv("BITGET_SECRET", ""),
                passphrase=os.getenv("BITGET_PASSPHRASE", ""),
                sandbox=os.getenv("BITGET_SANDBOX", "true").lower() == "true",
                trading_fee=0.001,
                min_order_size=0.001
            ),
            "mexc": ExchangeConfig(
                name="mexc",
                type=ExchangeType.CEX,
                api_key=os.getenv("MEXC_API_KEY", ""),
                secret=os.getenv("MEXC_SECRET", ""),
                sandbox=os.getenv("MEXC_SANDBOX", "true").lower() == "true",
                trading_fee=0.002,
                min_order_size=0.001
            ),
            "bitmart": ExchangeConfig(
                name="bitmart",
                type=ExchangeType.CEX,
                api_key=os.getenv("BITMART_API_KEY", ""),
                secret=os.getenv("BITMART_SECRET", ""),
                sandbox=os.getenv("BITMART_SANDBOX", "true").lower() == "true",
                trading_fee=0.0025,
                min_order_size=0.001
            ),
            "uniswap": ExchangeConfig(
                name="uniswap",
                type=ExchangeType.DEX,
                trading_fee=0.003,  # 0.3% for Uniswap V3
                min_order_size=0.001
            )
        }
        
        # SOR parameters
        self.max_slippage: float = float(os.getenv("SOR_MAX_SLIPPAGE", "0.005"))
        self.max_order_size: float = float(os.getenv("SOR_MAX_ORDER_SIZE", "10000.0"))
        self.min_order_size: float = float(os.getenv("SOR_MIN_ORDER_SIZE", "0.001"))
        self.min_liquidity_threshold: float = float(os.getenv("SOR_MIN_LIQUIDITY_THRESHOLD", "1000.0"))
        self.price_tolerance: float = float(os.getenv("SOR_PRICE_TOLERANCE", "0.001"))
        
        # Execution parameters
        self.execution_timeout: int = int(os.getenv("SOR_EXECUTION_TIMEOUT", "30"))
        self.max_retries: int = int(os.getenv("SOR_MAX_RETRIES", "3"))
        self.retry_delay: float = float(os.getenv("SOR_RETRY_DELAY", "1.0"))
        
        # Risk management
        self.max_daily_volume: float = float(os.getenv("SOR_MAX_DAILY_VOLUME", "100000.0"))
        self.max_position_size: float = float(os.getenv("SOR_MAX_POSITION_SIZE", "50000.0"))
        self.enable_risk_checks: bool = os.getenv("SOR_ENABLE_RISK_CHECKS", "true").lower() == "true"
        
        # Monitoring
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.enable_metrics: bool = os.getenv("SOR_ENABLE_METRICS", "true").lower() == "true"
        self.metrics_port: int = int(os.getenv("SOR_METRICS_PORT", "8080"))
        
        # Database
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///sor.db")
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")


# Global config instance
config = SORConfig()