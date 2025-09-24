#!/usr/bin/env python3
"""
Simple startup script for Railway deployment
"""

import os
import sys
import subprocess

def main():
    """Start the SOR application"""
    print("🚀 Starting Smart Order Router...")
    
    # Set default port if not provided
    port = os.environ.get('PORT', '8000')
    
    # Set environment variables
    os.environ['SOR_API_PORT'] = port
    
    # Start the application
    try:
        # Import and run the main application
        from main import main as run_main
        
        # Override sys.argv to pass the correct arguments
        sys.argv = ['main.py', '--mode', 'api', '--port', port]
        
        print(f"🌐 Starting server on port {port}")
        print(f"🔗 Health check will be available at: http://0.0.0.0:{port}/")
        run_main()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("📦 Installing dependencies...")
        
        # Try to install dependencies
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
        
        # Try again
        from main import main as run_main
        sys.argv = ['main.py', '--mode', 'api', '--port', port]
        print(f"🌐 Starting server on port {port}")
        run_main()
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("🔄 Trying alternative startup...")
        
        # Fallback: try direct uvicorn
        try:
            import uvicorn
            from api_server import app
            print(f"🌐 Starting with uvicorn on port {port}")
            uvicorn.run(app, host="0.0.0.0", port=int(port))
        except Exception as e2:
            print(f"❌ Fallback also failed: {e2}")
            sys.exit(1)

if __name__ == "__main__":
    main()
