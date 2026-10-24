from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.api.v1.tenants import router as tenants_router
from app.api.v1.parts import router as parts_router
from app.api.v1.bom import router as bom_router
from app.api.v1.ai import router as ai_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize pgvector extension and create all database tables
    init_db()
    yield


app = FastAPI(
    title="AI-Native Supply Chain SaaS Engine",
    description="Multi-tenant Hierarchical Bill of Materials (BOM) management with pgvector semantic search and recursive cost rollups.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenants_router, prefix="/api/v1")
app.include_router(parts_router, prefix="/api/v1")
app.include_router(bom_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "ai-native-scm-engine",
        "vector_dimensions": 768,
        "database": "PostgreSQL 16 + pgvector"
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to AI-Native SCM Engine API. Visit /docs for interactive Swagger UI."
    }
