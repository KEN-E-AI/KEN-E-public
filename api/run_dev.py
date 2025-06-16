#!/usr/bin/env python3
"""
Development server runner for Kene API.
"""

import uvicorn
from src.kene_api.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.kene_api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # Enable auto-reload for development
        log_level="info"
    )
