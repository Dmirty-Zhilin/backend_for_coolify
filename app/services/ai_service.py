import os
import json
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from app.services.openrouter_service import OpenRouterService
from app.services.mcp_link_adapter import MCPLinkAdapter

class AIService:
    """
    Сервис для работы с ИИ-моделями через OpenRouter API или MCP-Link.
    """
    
    def __init__(self):
        """Инициализация сервиса ИИ."""
        self.logger = logging.getLogger("ai_service")
        self.config_path = os.path.join("config", "ai_settings.json")
        self.settings = self._load_settings()
        
        # Инициализация OpenRouter сервиса
        self.openrouter_service = OpenRouterService(
            api_key=self.settings.get("api_key", ""),
            default_model=self.settings.get("default_model", "openai/gpt-3.5-turbo")
        )
        
        # Инициализация MCP-Link адаптера, если включен
        self.use_mcp_link = self.settings.get("use_mcp_link", False)
        self.mcp_link_adapter = None
        if self.use_mcp_link:
            mcp_server_url = self.settings.get("mcp_link_server_url", "http://localhost:8080")
            self.mcp_link_adapter = MCPLinkAdapter(mcp_server_url, self.openrouter_service)
    
    def _load_settings(self) -> Dict[str, Any]:
        """Загрузка настроек ИИ из конфигурационного файла."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r") as f:
                    return json.load(f)
            else:
                # Создаем файл с настройками по умолчанию
                default_settings = {
                    "api_key": "",
                    "default_model": "openai/gpt-3.5-turbo",
                    "use_mcp_link": False,
                    "mcp_link_server_url": "http://localhost:8080",
                    "custom_prompts": {
                        "domain_analysis": {
                            "system": "You are an expert in website content analysis...",
                            "user_template": "Analyze the following website content for domain {domain}:\\n\\n{content}"
                        }
                    },
                    "request_settings": {
                        "max_tokens": 1000,
                        "temperature": 0.7
                    }
                }
                os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                with open(self.config_path, "w") as f:
                    json.dump(default_settings, f, indent=2)
                return default_settings
        except Exception as e:
            self.logger.error(f"Error loading AI settings: {str(e)}")
            return {}
    
    def _save_settings(self) -> bool:
        """Сохранение настроек ИИ в конфигурационный файл."""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.settings, f, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"Error saving AI settings: {str(e)}")
            return False
    
    async def analyze_domain_content(self, domain: str, content: str, agent_type: str = "thematic") -> Dict[str, Any]:
        """
        Анализ содержимого домена с использованием ИИ.
        
        Args:
            domain: Доменное имя
            content: Текстовое содержимое для анализа
            agent_type: Тип агента для анализа (thematic, sentiment, audience, etc.)
            
        Returns:
            Результат анализа в виде словаря
        """
        if self.use_mcp_link and self.mcp_link_adapter:
            return await self.mcp_link_adapter.analyze_domain_content(domain, content, agent_type)
        else:
            # Прямой вызов OpenRouter API
            if agent_type == "thematic":
                return await self.openrouter_service.analyze_domain_content(domain, content)
            elif agent_type == "sentiment":
                return await self.openrouter_service.analyze_sentiment(domain, content)
            elif agent_type == "audience":
                return await self.openrouter_service.analyze_target_audience(domain, content)
            else:
                # Для неизвестных типов агентов используем базовый анализ
                return await self.openrouter_service.analyze_domain_content(domain, content)
    
    async def update_api_key(self, api_key: str) -> bool:
        """Обновление API ключа OpenRouter."""
        self.settings["api_key"] = api_key
        self.openrouter_service.api_key = api_key
        return self._save_settings()
    
    async def update_default_model(self, model: str) -> bool:
        """Обновление модели по умолчанию."""
        self.settings["default_model"] = model
        self.openrouter_service.default_model = model
        return self._save_settings()
    
    async def toggle_mcp_link(self, use_mcp_link: bool, server_url: Optional[str] = None) -> bool:
        """
        Включение/выключение использования MCP-Link.
        
        Args:
            use_mcp_link: Флаг использования MCP-Link
            server_url: URL MCP-Link сервера (опционально)
            
        Returns:
            True если настройки успешно обновлены, иначе False
        """
        self.settings["use_mcp_link"] = use_mcp_link
        
        if server_url:
            self.settings["mcp_link_server_url"] = server_url
        
        if use_mcp_link:
            mcp_server_url = self.settings.get("mcp_link_server_url", "http://localhost:8080")
            self.mcp_link_adapter = MCPLinkAdapter(mcp_server_url, self.openrouter_service)
        else:
            self.mcp_link_adapter = None
            
        return self._save_settings()
    
    async def list_available_agents(self) -> List[Dict[str, Any]]:
        """
        Получение списка доступных агентов.
        
        Returns:
            Список агентов с их описаниями и возможностями
        """
        if self.use_mcp_link and self.mcp_link_adapter:
            return await self.mcp_link_adapter.list_available_agents()
        else:
            # Если MCP-Link не используется, возвращаем предопределенный список базовых агентов
            return [
                {
                    "name": "thematic",
                    "description": "Анализ основной тематики и категории домена",
                    "capabilities": ["category_detection", "topic_extraction", "keyword_analysis"]
                },
                {
                    "name": "sentiment",
                    "description": "Анализ тональности и эмоциональной окраски контента",
                    "capabilities": ["sentiment_analysis", "emotion_detection"]
                },
                {
                    "name": "audience",
                    "description": "Определение целевой аудитории домена",
                    "capabilities": ["audience_profiling", "demographic_analysis"]
                }
            ]
    
    async def create_custom_agent(self, agent_name: str, agent_config: Dict[str, Any]) -> bool:
        """
        Создание пользовательского агента.
        
        Args:
            agent_name: Имя нового агента
            agent_config: Конфигурация агента (промпты, модель, параметры)
            
        Returns:
            True если агент успешно создан, иначе False
        """
        if self.use_mcp_link and self.mcp_link_adapter:
            return await self.mcp_link_adapter.create_custom_agent(agent_name, agent_config)
        else:
            # Если MCP-Link не используется, сохраняем конфигурацию агента локально
            if "custom_agents" not in self.settings:
                self.settings["custom_agents"] = {}
                
            self.settings["custom_agents"][agent_name] = agent_config
            return self._save_settings()
