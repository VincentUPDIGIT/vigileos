#!/usr/bin/env python3
"""
Network Monitoring Agent - Main Entry Point
"""

import sys
import asyncio
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.agent.main_agent import main

if __name__ == '__main__':
    asyncio.run(main())