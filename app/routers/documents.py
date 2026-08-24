from app.services.llm_service import generate_answer
from app.models import Document, DocumentChunk

from app.services.pdf_service import extract_text_from_pdf
from app.services.chunk_service import chunk_text
from pathlib import Path
from uuid import uuid4
from pydantic import BaseModel, Field

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.services.embedding_service import (
    generate_embeddings,
    generate_embedding
)



router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)

UPLOAD_DIR = Path("uploads/documents")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)

class AskRequest(BaseModel):
    question: str
    top_k: int = Field(default=3, ge=1, le=10)

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Only allow PDFs
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    contents = await file.read()

    # Reject empty files
    if not contents:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    # Maximum 10 MB
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size must be less than 10 MB"
        )

    stored_filename = f"{uuid4().hex}.pdf"
    file_path = UPLOAD_DIR / stored_filename

    try:
        # Save PDF
        with open(file_path, "wb") as buffer:
            buffer.write(contents)

        # Extract text
        try:
            extracted_text = extract_text_from_pdf(file_path)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Unable to read PDF. The file may be corrupted."
            )

        # Reject image-only / empty-text PDFs for now
        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No readable text found in PDF"
            )

        # Chunk document
        chunks = chunk_text(extracted_text)

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Unable to create document chunks"
            )

        # Generate embeddings
        try:
            embeddings = generate_embeddings(chunks)
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate document embeddings"
            )

        # Create document
        document = Document(
            filename=file.filename,
            file_path=str(file_path),
            content_type=file.content_type
        )

        db.add(document)

        # Get document.id without committing yet
        db.flush()

        # Save chunks + vectors
        for index, (chunk, embedding) in enumerate(
            zip(chunks, embeddings)
        ):
            document_chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=index,
                content=chunk,
                embedding=embedding
            )

            db.add(document_chunk)

        # Commit everything together
        db.commit()
        db.refresh(document)

        return {
            "message": "Document uploaded successfully",
            "document": {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "uploaded_at": document.uploaded_at
            },
            "extraction": {
                "characters_extracted": len(extracted_text),
                "chunks_created": len(chunks),
                "embeddings_stored": len(embeddings)
            }
        }

    except HTTPException:
        db.rollback()

        if file_path.exists():
            file_path.unlink()

        raise

    except Exception:
        db.rollback()

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Unexpected error while processing document"
        )

@router.post("/{document_id}/search")
def search_document(
    document_id: int,
    request: SearchRequest,
    db: Session = Depends(get_db)
):

    # Make sure the document exists
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    # Convert the user's question into a vector
    query_embedding = generate_embedding(request.query)

    # Calculate cosine distance
    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    # Find the closest chunks
    results = (
        db.query(
            DocumentChunk,
            distance.label("distance")
        )
        .filter(
            DocumentChunk.document_id == document_id
        )
        .order_by(distance)
        .limit(request.top_k)
        .all()
    )

    matches = []

    for chunk, distance_value in results:

        matches.append({
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "similarity": round(
                1 - float(distance_value),
                4
            )
        })

    return {
        "query": request.query,
        "document_id": document_id,
        "matches": matches
    }

@router.post("/{document_id}/ask")
def ask_document(
    document_id: int,
    request: AskRequest,
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    query_embedding = generate_embedding(
        request.question
    )

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding
    )

    results = (
        db.query(
            DocumentChunk,
            distance.label("distance")
        )
        .filter(
            DocumentChunk.document_id == document_id
        )
        .order_by(distance)
        .limit(request.top_k)
        .all()
    )

    contexts = [
        chunk.content
        for chunk, _ in results
    ]
    if not contexts:
        raise HTTPException(
            status_code=400,
            detail="No indexed content found for this document"
        ) 

    sources = []

    for source_number, (chunk, distance_value) in enumerate(
        results,
        start=1
    ):
        sources.append({
            "source": source_number,
            "chunk_index": chunk.chunk_index,
            "similarity": round(
                1 - float(distance_value),
                4
            ),
            "content": chunk.content
        })
    try:
        answer = generate_answer(
            question=request.question,
            contexts=contexts
        )
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="LLM service is currently unavailable"
        )

    return {
        "document_id": document_id,
        "filename": document.filename,
        "question": request.question,
        "answer": answer,
        "chunks_used": len(contexts),
        "sources": sources
    }

@router.get("")
def get_documents(
    db: Session = Depends(get_db)
):
    documents = (
        db.query(Document)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    return {
        "documents": [
            {
                "id": document.id,
                "filename": document.filename,
                "content_type": document.content_type,
                "uploaded_at": document.uploaded_at
            }
            for document in documents
        ]
    }

@router.get("/{document_id}")
def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    chunk_count = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .count()
    )

    return {
        "id": document.id,
        "filename": document.filename,
        "content_type": document.content_type,
        "uploaded_at": document.uploaded_at,
        "chunks": chunk_count
    }

@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    file_path = Path(document.file_path)

    # Delete document from database.
    # document_chunks are automatically removed
    # because of ON DELETE CASCADE.
    db.delete(document)
    db.commit()

    # Delete the actual PDF from disk
    if file_path.exists():
        file_path.unlink()

    return {
        "message": "Document deleted successfully",
        "document_id": document_id
    }