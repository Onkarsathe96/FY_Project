import os
import shutil
from typing import List
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.services.csv_store import InMemoryCSVStore
from app.config import DATA_DIR

router = APIRouter(prefix="/api/ingest", tags=["Ingestion"])
store = InMemoryCSVStore()

class IngestFileRequest(BaseModel):
    file_path: str

@router.get("/files")
def list_files():
    """Lists all available CSV files in the data directory."""
    return store.list_files()

@router.post("/process-single")
def load_single_csv(payload: IngestFileRequest):
    """Processes a single CSV from the local data folder."""
    try:
        return store.load_single_file(payload.file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_multiple_csvs(files: List[UploadFile] = File(...)):
    """Receives multiple drag-and-drop CSV files, saves them, and ingests them."""
    results = []
    for file in files:
        if not file.filename.endswith(".csv"):
            continue

        file_path = os.path.join(DATA_DIR, file.filename)
        
        # Save uploaded stream to disk safely
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Ingest directly into the analytics memory store
        try:
            res = store.load_single_file(file_path)
            results.append(res)
        except Exception as e:
            results.append({"file": file.filename, "status": "error", "detail": str(e)})

    return {
        "status": "success",
        "files_uploaded": len(results),
        "details": results
    }

@router.post("/reset-db")
def reset_store():
    """Clears in-memory dataset cache."""
    return store.clear()