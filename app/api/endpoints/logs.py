from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from io import BytesIO

from app.services.log_service import LogService

router = APIRouter()
log_service = LogService()

@router.get("/")
async def get_logs(
    limit: int = Query(100, description="Количество последних логов для отображения"),
    level: Optional[str] = Query(None, description="Фильтр по уровню логирования (INFO, WARNING, ERROR, DEBUG)")
):
    """Получение списка логов с возможностью фильтрации"""
    logs = await log_service.get_logs(limit=limit, level=level)
    return {"success": True, "logs": logs, "count": len(logs)}

@router.delete("/")
async def clear_logs():
    """Очистка логов"""
    result = await log_service.clear_logs()
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

@router.get("/download/{format}")
async def download_logs(format: str):
    """Скачивание логов в указанном формате"""
    if format not in ["txt", "json"]:
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats: txt, json")
    
    file_data = await log_service.download_logs(format=format)
    
    if not file_data:
        raise HTTPException(status_code=404, detail="Log file not found")
    
    # Определяем имя файла и MIME-тип
    filename = f"logs.{format}"
    media_type = "text/plain" if format == "txt" else "application/json"
    
    return StreamingResponse(
        file_data,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/")
async def add_log(level: str, message: str):
    """Добавление записи в лог"""
    if level not in ["INFO", "WARNING", "ERROR", "DEBUG"]:
        raise HTTPException(status_code=400, detail="Invalid log level. Supported levels: INFO, WARNING, ERROR, DEBUG")
    
    result = log_service.log(level=level, message=message)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    
    return result
