#!/usr/bin/env python3
"""
Debug script to check config and API keys
"""

import os
from config import config

def debug_config():
    """Debug the configuration"""
    
    print("🔍 Debugging Configuration...")
    print("-" * 50)
    
    # Check environment variables
    print("1. Environment Variables:")
    env_vars = [
        "GATEIO_API_KEY", "GATEIO_SECRET", "GATEIO_SANDBOX",
        "MEXC_API_KEY", "MEXC_SECRET", "MEXC_SANDBOX"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "NOT_SET")
        if "KEY" in var or "SECRET" in var:
            display_value = f"{value[:8]}..." if value != "NOT_SET" and len(value) > 8 else value
        else:
            display_value = value
        print(f"   {var}: {display_value}")
    
    print()
    
    # Check config object
    print("2. Config Object:")
    print(f"   Has exchanges: {hasattr(config, 'exchanges')}")
    if hasattr(config, 'exchanges'):
        print(f"   Exchange keys: {list(config.exchanges.keys())}")
        
        for exchange_name, exchange_config in config.exchanges.items():
            print(f"\n   {exchange_name.upper()}:")
            print(f"     API Key: {exchange_config.api_key[:8] if exchange_config.api_key else 'None'}...")
            print(f"     Secret: {exchange_config.secret[:8] if exchange_config.secret else 'None'}...")
            print(f"     Sandbox: {exchange_config.sandbox}")
            print(f"     Enabled: {exchange_config.enabled}")
    
    print()
    
    # Test if .get() method works
    print("3. Testing .get() method:")
    if hasattr(config, 'exchanges') and 'gateio' in config.exchanges:
        gateio_config = config.exchanges['gateio']
        try:
            api_key = gateio_config.get('api_key', '')
            secret = gateio_config.get('secret', '')
            sandbox = gateio_config.get('sandbox', True)
            print(f"   .get() method works: api_key={api_key[:8] if api_key else 'None'}...")
        except Exception as e:
            print(f"   .get() method failed: {e}")
    
    print()
    print("🎉 Debug complete!")

if __name__ == "__main__":
    debug_config()
