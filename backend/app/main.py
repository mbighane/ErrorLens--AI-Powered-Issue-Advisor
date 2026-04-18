from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api.issues import router as issues_router

app = FastAPI(
    title="ErrorLens API",
    description="AI-Powered Azure DevOps Issue Solver",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(issues_router, prefix="/api/issues", tags=["issues"])

@app.get("/")
async def root():
    return {"message": "ErrorLens API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}