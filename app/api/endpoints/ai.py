from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
import os

from app.services.ai_service import OpenRouterService

router = APIRouter()
ai_service = OpenRouterService()

@router.get("/models")
async def get_available_models(force_refresh: bool = Query(False, description="Принудительное обновление кэша моделей")):
    """Получение списка доступных моделей из OpenRouter API"""
    models = await ai_service.get_available_models(force_refresh=force_refresh)
    if not models:
        return {"success": False, "error": "Could not fetch available models", "models": []}
    return {"success": True, "models": models}

@router.post("/key")
async def update_api_key(api_key: str = Body(..., embed=True)):
    """Обновление API ключа OpenRouter"""
    result = await ai_service.update_api_key(api_key)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@router.post("/model")
async def update_default_model(model_name: str = Body(..., embed=True)):
    """Обновление модели по умолчанию"""
    result = await ai_service.update_model(model_name)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@router.post("/prompt")
async def update_prompt(
    prompt_type: str = Body(...),
    system_prompt: str = Body(...),
    user_template: str = Body(...)
):
    """Обновление промпта для определенного типа анализа"""
    result = await ai_service.update_prompt(prompt_type, system_prompt, user_template)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@router.post("/analyze/domain")
async def analyze_domain_content(
    domain: str = Body(...),
    content: str = Body(...),
    model: Optional[str] = Body(None)
):
    """Анализ содержимого домена с помощью AI"""
    result = await ai_service.get_thematic_analysis(content, domain, model)
    if "error" in result and result["error"]:
        return {"success": False, "error": result["error"], "analysis": result}
    return {"success": True, "analysis": result}

@router.post("/analyze/domains")
async def analyze_domains_batch(
    domains: List[str] = Body(...),
    model: Optional[str] = Body(None)
):
    """Анализ пакета доменов для категоризации"""
    result = await ai_service.analyze_domains_batch(domains, model)
    if "error" in result and result["error"]:
        return {"success": False, "error": result["error"], "analysis": result}
    return {"success": True, "analysis": result}

@router.get("/settings")
async def get_ai_settings():
    """Получение текущих настроек AI"""
    settings = await ai_service.get_settings()
    return {"success": True, "settings": settings}

@router.post("/settings/request")
async def update_request_settings(settings: Dict[str, Any] = Body(...)):
    """Обновление настроек запросов к AI"""
    result = await ai_service.update_request_settings(settings)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@router.post("/agent")
async def create_custom_agent(
    agent_name: str = Body(...),
    system_prompt: str = Body(...),
    training_data: List[Dict[str, str]] = Body(...)
):
    """Создание пользовательского агента с обучением на примерах"""
    result = await ai_service.create_custom_agent(agent_name, system_prompt, training_data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@router.put("/agent/{agent_name}")
async def update_custom_agent(
    agent_name: str,
    system_prompt: Optional[str] = Body(None),
    training_data: Optional[List[Dict[str, str]]] = Body(None)
):
    """Обновление пользовательского агента"""
    result = await ai_service.update_custom_agent(agent_name, system_prompt, training_data)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    return result

@router.delete("/agent/{agent_name}")
async def delete_custom_agent(agent_name: str):
    """Удаление пользовательского агента"""
    result = await ai_service.delete_custom_agent(agent_name)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Unknown error"))
    return result

@router.post("/agent/{agent_name}/query")
async def use_custom_agent(
    agent_name: str,
    query: str = Body(...),
    model: Optional[str] = Body(None)
):
    """Использование пользовательского агента для ответа на запрос"""
    result = await ai_service.use_custom_agent(agent_name, query, model)
    if "error" in result and result["error"]:
        return {"success": False, "error": result["error"], "result": result}
    return {"success": True, "result": result}
