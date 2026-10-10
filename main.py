import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure backend directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.router import api_router

app = FastAPI(
    title="Flood Evacuation Route Planner API",
    description="Emergency decision-support routing engine using Dijkstra/A* with dynamic flood risk penalties.",
    version="1.0.0",
)

# CORS configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "system": "Flood Evacuation Route Planner",
        "tagline": "When roads become unsafe, find the safer way out.",
        "status": "online",
        "api_docs": "/docs",
        "disclaimer": (
            "Prototype decision-support system. Does not provide real-time automated flood "
            "prediction. Uses user-reported or simulated hydrologic data."
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
