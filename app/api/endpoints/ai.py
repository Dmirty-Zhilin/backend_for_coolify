from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List, Optional
from app.services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

@router.get("/models")
async def get_available_models():
    """Получение списка доступных моделей."""
    # Здесь можно добавить логику получения списка моделей из OpenRouter
    return {
        "models": [
            "openai/gpt-3.5-turbo",
            "openai/gpt-4",
            "anthropic/claude-2",
            "google/palm"
        ]
    }

@router.post("/key")
async def update_api_key(api_key: str = Body(..., embed=True)):
    """Обновление API ключа OpenRouter."""
    success = await ai_service.update_api_key(api_key)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update API key")
    return {"status": "success"}

@router.post("/model")
async def update_default_model(model: str = Body(..., embed=True)):
    """Обновление модели по умолчанию."""
    success = await ai_service.update_default_model(model)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update default model")
    return {"status": "success"}

@router.post("/analyze/domain")
async def analyze_domain(domain: str = Body(...), content: str = Body(...), agent_type: str = Body("thematic")):
    """
    Анализ содержимого домена с использованием ИИ.
    
    Args:
        domain: Доменное имя
        content: Текстовое содержимое для анализа
        agent_type: Тип агента для анализа (thematic, sentiment, audience, etc.)
    """
    result = await ai_service.analyze_domain_content(domain, content, agent_type)
    return result

@router.get("/settings")
async def get_ai_settings():
    """Получение текущих настроек ИИ."""
    # Удаляем API ключ из ответа для безопасности
    settings = ai_service.settings.copy()
    if "api_key" in settings:
        settings["api_key"] = "***" if settings["api_key"] else ""
    return settings

@router.post("/settings/mcp-link")
async def toggle_mcp_link(use_mcp_link: bool = Body(...), server_url: Optional[str] = Body(None)):
    """
    Включение/выключение использования MCP-Link.
    
    Args:
        use_mcp_link: Флаг использования MCP-Link
        server_url: URL MCP-Link сервера (опционально)
    """
    success = await ai_service.toggle_mcp_link(use_mcp_link, server_url)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update MCP-Link settings")
    return {"status": "success", "use_mcp_link": use_mcp_link}

@router.get("/agents")
async def list_available_agents():
    """Получение списка доступных агентов."""
    agents = await ai_service.list_available_agents()
    return {"agents": agents}

@router.post("/agent")
async def create_custom_agent(agent_name: str = Body(...), agent_config: Dict[str, Any] = Body(...)):
    """
    Создание пользовательского агента.
    
    Args:
        agent_name: Имя нового агента
        agent_config: Конфигурация агента (промпты, модель, параметры)
    """
    success = await ai_service.create_custom_agent(agent_name, agent_config)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create custom agent")
    return {"status": "success", "agent_name": agent_name}

@router.post("/agent/{agent_name}/query")
async def query_agent(
    agent_name: str,
    domain: str = Body(...),
    content: str = Body(...)
):
    """
    Запрос к конкретному агенту.
    
    Args:
        agent_name: Имя агента
        domain: Доменное имя
        content: Текстовое содержимое для анализа
    """
    result = await ai_service.analyze_domain_content(domain, content, agent_name)
    return result
