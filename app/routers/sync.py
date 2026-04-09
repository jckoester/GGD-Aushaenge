import subprocess
import sys
from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth_dep

router = APIRouter(prefix="/sync", tags=["sync"], dependencies=[Depends(require_auth_dep)])


@router.post("/run", status_code=200)
def trigger_sync():
    """Löst den Sync-Job manuell aus (für Tests)."""
    result = subprocess.run(
        [sys.executable, "sync.py"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)
    return {"status": "ok", "output": result.stdout}
