"""
Main application entry point for Smart Order Router
Supports both Streamlit UI and FastAPI server modes
"""

import asyncio
import os
import sys
import argparse
import logging
from typing import Optional

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_streamlit_ui():
    """Run the Streamlit UI"""
    try:
        import streamlit.web.cli as stcli
        import sys
        
        # Set Streamlit config
        os.environ["STREAMLIT_SERVER_PORT"] = "8501"
        os.environ["STREAMLIT_SERVER_ADDRESS"] = "0.0.0.0"
        os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"
        os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        
        # Run Streamlit
        sys.argv = ["streamlit", "run", "sor_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
        stcli.main()
        
    except ImportError:
        logger.error("Streamlit not installed. Install with: pip install streamlit")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to run Streamlit UI: {e}")
        sys.exit(1)

def run_api_server():
    """Run the FastAPI server"""
    try:
        import uvicorn
        from api_server import app
        
        # Run FastAPI server
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level=config.log_level.lower(),
            access_log=True
        )
        
    except ImportError:
        logger.error("FastAPI dependencies not installed. Install with: pip install fastapi uvicorn")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to run API server: {e}")
        sys.exit(1)

def run_sor_direct():
    """Run SOR directly without UI"""
    try:
        from smart_order_router import SmartOrderRouter
        from models import OrderSide, OrderType
        from decimal import Decimal
        
        async def main():
            # Initialize SOR
            sor = SmartOrderRouter()
            await sor.initialize()
            await sor.start()
            
            try:
                logger.info("SOR started successfully")
                logger.info("Available exchanges: %s", list(sor.exchanges.keys()))
                
                # Example: Get best prices
                best_prices = await sor.get_best_prices("BTC/USDT")
                logger.info("Best prices for BTC/USDT: %s", best_prices)
                
                # Example: Find arbitrage opportunities
                opportunities = await sor.get_arbitrage_opportunities("BTC/USDT")
                logger.info("Arbitrage opportunities: %s", len(opportunities))
                
                # Keep running
                logger.info("SOR is running. Press Ctrl+C to stop.")
                while True:
                    await asyncio.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Shutting down SOR...")
            finally:
                await sor.stop()
                logger.info("SOR stopped")
        
        # Run the async main function
        asyncio.run(main())
        
    except ImportError as e:
        logger.error(f"Failed to import SOR modules: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to run SOR: {e}")
        sys.exit(1)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Smart Order Router")
    parser.add_argument(
        "--mode",
        choices=["ui", "api", "direct"],
        default="api",
        help="Run mode: ui (Streamlit), api (FastAPI), or direct (SOR only)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run on (for API mode)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=config.log_level.upper(),
        help="Log level"
    )
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("Starting Smart Order Router in %s mode", args.mode)
    
    if args.mode == "ui":
        run_streamlit_ui()
    elif args.mode == "api":
        # Update port if specified
        if args.port != 8000:
            os.environ["SOR_API_PORT"] = str(args.port)
        run_api_server()
    elif args.mode == "direct":
        run_sor_direct()
    else:
        logger.error("Invalid mode: %s", args.mode)
        sys.exit(1)

if __name__ == "__main__":
    main()