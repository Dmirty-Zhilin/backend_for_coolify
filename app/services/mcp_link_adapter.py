import os
import logging
import aiohttp
import json
from typing import Dict, Any, Optional, List

class MCPLinkAdapter:
    """
    Адаптер для взаимодействия с MCP-Link сервером.
    Позволяет использовать ИИ-агентов через MCP-протокол.
    """
    
    def __init__(self, mcp_server_url: str, openrouter_service=None):
        """
        Инициализация адаптера MCP-Link.
        
        Args:
            mcp_server_url: URL MCP-Link сервера
            openrouter_service: Экземпляр сервиса OpenRouter для прямых вызовов
        """
        self.mcp_server_url = mcp_server_url
        self.openrouter_service = openrouter_service
        self.logger = logging.getLogger("mcp_link_adapter")
        
    async def analyze_domain_content(self, domain: str, content: str, agent_type: str = "thematic") -> Dict[str, Any]:
        """
        Анализ содержимого домена с использованием MCP-Link агента.
        
        Args:
            domain: Доменное имя
            content: Текстовое содержимое для анализа
            agent_type: Тип агента для анализа (thematic, sentiment, audience, etc.)
            
        Returns:
            Результат анализа в виде словаря
        """
        try:
            # Формируем запрос к MCP-Link серверу
            payload = {
                "function": f"analyze_{agent_type}",
                "arguments": {
                    "domain": domain,
                    "content": content
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.mcp_server_url}/run", json=payload) as response:
                    if response.status != 200:
                        self.logger.error(f"MCP-Link server error: {response.status}, {await response.text()}")
                        # Fallback на прямой вызов OpenRouter
                        return await self._fallback_to_openrouter(domain, content, agent_type)
                    
                    result = await response.json()
                    return result
                    
        except Exception as e:
            self.logger.error(f"Error calling MCP-Link server: {str(e)}")
            # Fallback на прямой вызов OpenRouter
            return await self._fallback_to_openrouter(domain, content, agent_type)
    
    async def _fallback_to_openrouter(self, domain: str, content: str, agent_type: str) -> Dict[str, Any]:
        """
        Резервный метод для прямого вызова OpenRouter API в случае ошибки MCP-Link.
        
        Args:
            domain: Доменное имя
            content: Текстовое содержимое для анализа
            agent_type: Тип агента для анализа
            
        Returns:
            Результат анализа в виде словаря
        """
        self.logger.info(f"Falling back to direct OpenRouter call for {domain}")
        
        if not self.openrouter_service:
            return {"error": "OpenRouter service not available for fallback"}
        
        if agent_type == "thematic":
            return await self.openrouter_service.analyze_domain_content(domain, content)
        elif agent_type == "sentiment":
            return await self.openrouter_service.analyze_sentiment(domain, content)
        elif agent_type == "audience":
            return await self.openrouter_service.analyze_target_audience(domain, content)
        else:
            # Для неизвестных типов агентов используем базовый анализ
            return await self.openrouter_service.analyze_domain_content(domain, content)
            
    async def list_available_agents(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных агентов из MCP-Link сервера.
        
        Returns:
            Список агентов с их описаниями и возможностями
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_server_url}/agents") as response:
                    if response.status != 200:
                        self.logger.error(f"Error getting agents list: {response.status}")
                        return []
                    
                    result = await response.json()
                    return result.get("agents", [])
        except Exception as e:
            self.logger.error(f"Error listing MCP-Link agents: {str(e)}")
            return []
            
    async def create_custom_agent(self, agent_name: str, agent_config: Dict[str, Any]) -> bool:
        """
        Создание пользовательского агента в MCP-Link.
        
        Args:
            agent_name: Имя нового агента
            agent_config: Конфигурация агента (промпты, модель, параметры)
            
        Returns:
            True если агент успешно создан, иначе False
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.mcp_server_url}/agents/create",
                    json={"name": agent_name, "config": agent_config}
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"Error creating agent: {response.status}, {await response.text()}")
                        return False
                    
                    return True
        except Exception as e:
            self.logger.error(f"Error creating MCP-Link agent: {str(e)}")
            return False
