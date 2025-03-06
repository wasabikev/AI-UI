#run.py

import asyncio
from hypercorn.config import Config
from hypercorn.asyncio import serve
from app import app
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def main():
    config = Config()
    config.bind = [f"127.0.0.1:5000"]  # Local development binding
    config.use_reloader = True  # Enable auto-reload for development
    
    # Set the number of workers (use 1 for development)
    config.workers = 1
    
    # Enable debug mode for development
    app.debug = True
    
    # Start the server
    await serve(app, config)

if __name__ == "__main__":
    asyncio.run(main())