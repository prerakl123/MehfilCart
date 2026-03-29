"""Private router -- internal utilities and script execution."""

import asyncio
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/private", tags=["Private"])

# Define the path to the standalone_scripts directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = BASE_DIR / "standalone_scripts"

@router.post(
    "/run-script/{script_name}",
    summary="Run a Standalone Script",
    description="Executes a python script located in the standalone_scripts directory using the active environment.",
)
async def run_standalone_script(script_name: str):
    """
    Executes a script from the standalone_scripts directory as a subprocess.
    Returns the stdout and stderr.
    """
    if not script_name.endswith(".py"):
        script_name += ".py"

    script_path = SCRIPTS_DIR / script_name

    # Security check to prevent directory traversal attacks
    try:
        resolved_script_path = script_path.resolve()
        resolved_scripts_dir = SCRIPTS_DIR.resolve()
        
        if resolved_scripts_dir not in resolved_script_path.parents:
            raise HTTPException(status_code=400, detail="Invalid script name: directory traversal detected")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid script name")

    if not script_path.exists() or not script_path.is_file():
        raise HTTPException(status_code=404, detail="Script not found")

    # Run the script using the current virtual environment's python executable
    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(BASE_DIR)
    )
    
    # Wait for the script to finish
    stdout, stderr = await proc.communicate()
    
    return {
        "script_name": script_name,
        "return_code": proc.returncode,
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
    }
