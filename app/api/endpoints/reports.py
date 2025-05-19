from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, UploadFile, File, Depends
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Optional
import os
import asyncio
from datetime import datetime
import uuid

from app.models.report_models import (
    ReportGenerateRequest,
    ReportResponse,
    ReportDownloadResponse
)
from app.services.report_service import ReportService

router = APIRouter()
report_service = ReportService()

@router.post("/generate", response_model=ReportResponse)
async def generate_report(
    request: ReportGenerateRequest,
    background_tasks: BackgroundTasks
):
    """Генерация отчета для списка доменов"""
    if not request.domains:
        raise HTTPException(status_code=400, detail="No domains provided")
    
    # Запускаем генерацию отчета в фоновом режиме
    result = await report_service.generate_report(
        domains=request.domains,
        match_type=request.match_type,
        collapse=request.collapse,
        limit=request.limit,
        concurrency=request.concurrency
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    
    return ReportResponse(
        success=result["success"],
        domains_count=result["domains_count"],
        analyzed_count=result["analyzed_count"],
        long_live_count=result.get("long_live_count", 0),
        execution_time_sec=result["execution_time_sec"],
        report_paths=result["report_paths"]
    )

@router.get("/drop_report", response_model=ReportResponse)
async def get_drop_report():
    """Получение общего отчета"""
    result = await report_service.get_report(report_type="drop_report")
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Report not found"))
    
    return ReportResponse(
        success=result["success"],
        domains_count=result["domains_count"],
        report_data=result["report_data"],
        report_paths=result["report_paths"]
    )

@router.get("/drop_report_long_live", response_model=ReportResponse)
async def get_drop_report_long_live():
    """Получение отчета качественного дропа"""
    result = await report_service.get_report(report_type="drop_report_long_live")
    
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Report not found"))
    
    return ReportResponse(
        success=result["success"],
        domains_count=result["domains_count"],
        report_data=result["report_data"],
        report_paths=result["report_paths"]
    )

@router.get("/download/{report_type}/{format}")
async def download_report(report_type: str, format: str):
    """Скачивание отчета в указанном формате"""
    if report_type not in ["drop_report", "drop_report_long_live"]:
        raise HTTPException(status_code=400, detail="Invalid report type")
    
    if format not in ["csv", "excel"]:
        raise HTTPException(status_code=400, detail="Invalid format")
    
    file_data = await report_service.download_report(report_type=report_type, format=format)
    
    if not file_data:
        raise HTTPException(status_code=404, detail="Report file not found")
    
    # Определяем имя файла и MIME-тип
    filename = f"{report_type}.{format}"
    media_type = "text/csv" if format == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return StreamingResponse(
        file_data,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.post("/upload", response_model=ReportResponse)
async def upload_domains_file(file: UploadFile = File(...)):
    """Загрузка файла со списком доменов и генерация отчета"""
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    # Проверяем расширение файла
    if not file.filename.endswith(('.txt', '.csv')):
        raise HTTPException(status_code=400, detail="Only .txt and .csv files are supported")
    
    # Создаем временный файл для сохранения загруженного списка доменов
    temp_file_path = f"temp_domains_{uuid.uuid4()}.txt"
    
    try:
        # Читаем содержимое файла
        contents = await file.read()
        
        # Сохраняем во временный файл
        with open(temp_file_path, "wb") as f:
            f.write(contents)
        
        # Читаем домены из файла
        with open(temp_file_path, "r") as f:
            domains = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        # Удаляем временный файл
        os.remove(temp_file_path)
        
        if not domains:
            raise HTTPException(status_code=400, detail="No valid domains found in the file")
        
        # Генерируем отчет
        result = await report_service.generate_report(domains=domains)
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return ReportResponse(
            success=result["success"],
            domains_count=result["domains_count"],
            analyzed_count=result["analyzed_count"],
            long_live_count=result.get("long_live_count", 0),
            execution_time_sec=result["execution_time_sec"],
            report_paths=result["report_paths"]
        )
    
    except Exception as e:
        # Удаляем временный файл в случае ошибки
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
