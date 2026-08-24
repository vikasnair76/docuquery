
from fastapi import FastAPI
from sqlalchemy import text

from app.database import engine, Base
from app import models

from app.routers.documents import router as documents_router

Base.metadata.create_all(bind=engine)



app = FastAPI(
    title="DocuQuery API",
    description="AI-powered document question answering using RAG",
    version="1.0.0"
)

app.include_router(documents_router)


@app.get("/")
def root():
    return {
        "message": "DocuQuery API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/db-test")
def test_database():

    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT 1")
        )

        value = result.scalar()

    return {
        "database": "connected",
        "result": value
    }