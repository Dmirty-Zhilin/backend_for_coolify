import os
import json
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Configure a basic logger for this module if not configured globally
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class OpenRouterService:
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 model_name: str = "openai/gpt-3.5-turbo",
                 config_path: str = "config/ai_settings.json"):
        """
        Инициализация сервиса OpenRouter с расширенными настройками
        
        Args:
            api_key: API ключ для OpenRouter
            model_name: Имя модели по умолчанию
            config_path: Путь к файлу конфигурации
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            logger.warning("OpenRouter API key is not set. AI features will not work.")
        
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_name = model_name
        self.config_path = config_path
        
        # Создаем директорию для конфигурации, если она не существует
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        # Загружаем настройки из файла конфигурации
        self.settings = self.load_settings()
        
        # Кэш доступных моделей
        self._models_cache = None
        self._models_cache_time = 0

    def load_settings(self) -> Dict[str, Any]:
        """Загрузка настроек из файла конфигурации"""
        default_settings = {
            "api_key": self.api_key,
            "default_model": self.model_name,
            "custom_prompts": {
                "domain_analysis": {
                    "system": "You are an expert in website content analysis. Analyze the following text from a website and provide a concise thematic summary. Identify the main topics, keywords (up to 10), and suggest a primary category for the website (e.g., E-commerce, Blog, News, Corporate, Technology, Health, etc.). Respond in JSON format with keys: 'primary_category', 'main_topics' (list of strings), 'keywords' (list of strings), and 'summary' (a brief text summary).",
                    "user_template": "Analyze the following website content for domain {domain}:\n\n{content}"
                },
                "domain_categorization": {
                    "system": "You are an expert in domain name analysis. Analyze the following domain names and categorize them based on their potential use cases, industries, and value. Respond in JSON format with an array of objects, each containing 'domain', 'category', 'industry', 'value_rating' (1-10), and 'notes'.",
                    "user_template": "Analyze and categorize the following domain names:\n\n{domains}"
                }
            },
            "custom_agents": {},
            "request_settings": {
                "max_tokens": 1000,
                "temperature": 0.7,
                "timeout_seconds": 60,
                "max_content_length": 15000
            }
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_settings = json.load(f)
                    # Обновляем дефолтные настройки загруженными
                    self._deep_update(default_settings, loaded_settings)
                    logger.info(f"AI settings loaded from {self.config_path}")
            else:
                # Если файл не существует, создаем его с дефолтными настройками
                with open(self.config_path, 'w') as f:
                    json.dump(default_settings, f, indent=2)
                    logger.info(f"Created default AI settings at {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading AI settings: {e}")
        
        return default_settings

    def _deep_update(self, d: Dict, u: Dict) -> Dict:
        """Рекурсивное обновление словаря"""
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
        return d

    def save_settings(self) -> bool:
        """Сохранение настроек в файл конфигурации"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.settings, f, indent=2)
            logger.info(f"AI settings saved to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving AI settings: {e}")
            return False

    async def get_available_models(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Получение списка доступных моделей из OpenRouter API
        
        Args:
            force_refresh: Принудительное обновление кэша моделей
            
        Returns:
            Список доступных моделей
        """
        import time
        
        # Проверяем кэш (обновляем раз в час)
        current_time = time.time()
        if not force_refresh and self._models_cache and (current_time - self._models_cache_time < 3600):
            return self._models_cache
        
        if not self.api_key:
            logger.warning("OpenRouter API key is not set. Cannot fetch available models.")
            return []
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/models", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("data", [])
                        
                        # Кэшируем результат
                        self._models_cache = models
                        self._models_cache_time = current_time
                        
                        return models
                    else:
                        error_details = await response.text()
                        logger.error(f"OpenRouter API error when fetching models (Status {response.status}): {error_details}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching available models: {e}")
            return []

    async def update_api_key(self, api_key: str) -> Dict[str, Any]:
        """
        Обновление API ключа и проверка его валидности
        
        Args:
            api_key: Новый API ключ
            
        Returns:
            Результат операции
        """
        if not api_key:
            return {"success": False, "error": "API key cannot be empty"}
        
        # Сохраняем текущий ключ для восстановления в случае ошибки
        old_api_key = self.api_key
        
        # Устанавливаем новый ключ
        self.api_key = api_key
        
        # Проверяем валидность ключа, запрашивая список моделей
        try:
            models = await self.get_available_models(force_refresh=True)
            if models:
                # Ключ валидный, обновляем настройки
                self.settings["api_key"] = api_key
                self.save_settings()
                return {"success": True, "message": "API key updated successfully", "models_count": len(models)}
            else:
                # Ключ невалидный, восстанавливаем старый
                self.api_key = old_api_key
                return {"success": False, "error": "Invalid API key. Could not fetch models."}
        except Exception as e:
            # Ошибка при проверке, восстанавливаем старый ключ
            self.api_key = old_api_key
            logger.error(f"Error validating API key: {e}")
            return {"success": False, "error": f"Error validating API key: {str(e)}"}

    async def update_model(self, model_name: str) -> Dict[str, Any]:
        """
        Обновление модели по умолчанию
        
        Args:
            model_name: Имя новой модели
            
        Returns:
            Результат операции
        """
        if not model_name:
            return {"success": False, "error": "Model name cannot be empty"}
        
        # Проверяем, существует ли такая модель
        models = await self.get_available_models()
        model_ids = [model.get("id") for model in models]
        
        if not models:
            return {"success": False, "error": "Could not fetch available models to validate"}
        
        if model_name not in model_ids:
            return {"success": False, "error": f"Model '{model_name}' not found in available models", "available_models": model_ids}
        
        # Обновляем модель
        self.model_name = model_name
        self.settings["default_model"] = model_name
        self.save_settings()
        
        return {"success": True, "message": f"Default model updated to {model_name}"}

    async def update_prompt(self, prompt_type: str, system_prompt: str, user_template: str) -> Dict[str, Any]:
        """
        Обновление промпта для определенного типа анализа
        
        Args:
            prompt_type: Тип промпта (domain_analysis, domain_categorization, etc.)
            system_prompt: Системный промпт
            user_template: Шаблон пользовательского промпта
            
        Returns:
            Результат операции
        """
        if not prompt_type or not system_prompt or not user_template:
            return {"success": False, "error": "Prompt type, system prompt, and user template cannot be empty"}
        
        # Обновляем промпт
        if prompt_type not in self.settings["custom_prompts"]:
            self.settings["custom_prompts"][prompt_type] = {}
        
        self.settings["custom_prompts"][prompt_type]["system"] = system_prompt
        self.settings["custom_prompts"][prompt_type]["user_template"] = user_template
        
        self.save_settings()
        
        return {"success": True, "message": f"Prompt for {prompt_type} updated successfully"}

    async def get_thematic_analysis(self, text_content: str, domain: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Выполняет тематический анализ текста с использованием OpenRouter
        
        Args:
            text_content: Текст для анализа
            domain: Домен, для которого выполняется анализ
            model: Модель для использования (если None, используется модель по умолчанию)
            
        Returns:
            Результат анализа
        """
        if not self.api_key:
            return {"error": "OpenRouter API key not configured."}
        if not text_content or text_content.isspace():
            return {"error": "No content provided for thematic analysis."}

        # Используем указанную модель или модель по умолчанию
        model_to_use = model or self.model_name
        
        # Получаем настройки промпта
        prompt_settings = self.settings["custom_prompts"].get("domain_analysis", {})
        system_prompt = prompt_settings.get("system", "You are an expert in website content analysis...")
        user_template = prompt_settings.get("user_template", "Analyze the following website content for domain {domain}:\n\n{content}")
        
        # Получаем настройки запроса
        request_settings = self.settings["request_settings"]
        max_content_length = request_settings.get("max_content_length", 15000)
        timeout_seconds = request_settings.get("timeout_seconds", 60)
        max_tokens = request_settings.get("max_tokens", 1000)
        temperature = request_settings.get("temperature", 0.7)

        # Обрезаем текст, если он слишком длинный
        if len(text_content) > max_content_length:
            logger.info(f"Content for {domain} is too long ({len(text_content)} chars), truncating to {max_content_length} chars for thematic analysis.")
            text_content = text_content[:max_content_length]

        # Формируем пользовательский промпт
        user_prompt = user_template.format(domain=domain, content=text_content)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        analysis_result = {
            "domain": domain,
            "model_used": model_to_use,
            "primary_category": None,
            "main_topics": [],
            "keywords": [],
            "summary": None,
            "error": None
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", 
                                        headers=headers, 
                                        json=payload, 
                                        timeout=timeout_seconds) as response:
                    if response.status == 200:
                        data = await response.json()
                        message_content = data.get("choices", [{}])[0].get("message", {}).get("content")
                        if message_content:
                            try:
                                # Парсим JSON-ответ
                                parsed_content = await asyncio.to_thread(json.loads, message_content)
                                analysis_result["primary_category"] = parsed_content.get("primary_category")
                                analysis_result["main_topics"] = parsed_content.get("main_topics", [])
                                analysis_result["keywords"] = parsed_content.get("keywords", [])
                                analysis_result["summary"] = parsed_content.get("summary")
                            except json.JSONDecodeError as je:
                                logger.error(f"Failed to parse JSON response from OpenRouter for {domain}: {je}. Content: {message_content}")
                                analysis_result["error"] = "Failed to parse LLM response. Content was not valid JSON."
                                analysis_result["summary"] = message_content
                        else:
                            analysis_result["error"] = "No content in OpenRouter response message."
                            logger.warning(f"No content in OpenRouter response for {domain}: {data}")
                    else:
                        error_details = await response.text()
                        logger.error(f"OpenRouter API error for {domain} (Status {response.status}): {error_details}")
                        analysis_result["error"] = f"OpenRouter API error: {response.status} - {error_details[:200]}"
        except aiohttp.ClientConnectorError as e:
            logger.error(f"Connection error with OpenRouter for {domain}: {e}")
            analysis_result["error"] = f"OpenRouter connection error: {e}"
        except asyncio.TimeoutError:
            logger.error(f"Timeout error when calling OpenRouter for {domain}")
            analysis_result["error"] = "OpenRouter request timed out."
        except Exception as e:
            logger.exception(f"Unexpected error during OpenRouter thematic analysis for {domain}: {e}")
            analysis_result["error"] = f"An unexpected error occurred: {str(e)}"
        
        return analysis_result

    async def analyze_domains_batch(self, domains: List[str], model: Optional[str] = None) -> Dict[str, Any]:
        """
        Анализ пакета доменов для категоризации
        
        Args:
            domains: Список доменов для анализа
            model: Модель для использования (если None, используется модель по умолчанию)
            
        Returns:
            Результат анализа
        """
        if not self.api_key:
            return {"error": "OpenRouter API key not configured."}
        if not domains:
            return {"error": "No domains provided for analysis."}

        # Используем указанную модель или модель по умолчанию
        model_to_use = model or self.model_name
        
        # Получаем настройки промпта
        prompt_settings = self.settings["custom_prompts"].get("domain_categorization", {})
        system_prompt = prompt_settings.get("system", "You are an expert in domain name analysis...")
        user_template = prompt_settings.get("user_template", "Analyze and categorize the following domain names:\n\n{domains}")
        
        # Получаем настройки запроса
        request_settings = self.settings["request_settings"]
        timeout_seconds = request_settings.get("timeout_seconds", 60)
        max_tokens = request_settings.get("max_tokens", 1000)
        temperature = request_settings.get("temperature", 0.7)

        # Формируем список доменов для промпта
        domains_text = "\n".join(domains)
        
        # Формируем пользовательский промпт
        user_prompt = user_template.format(domains=domains_text)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        analysis_result = {
            "domains": domains,
            "model_used": model_to_use,
            "categorization": [],
            "error": None
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", 
                                        headers=headers, 
                                        json=payload, 
                                        timeout=timeout_seconds) as response:
                    if response.status == 200:
                        data = await response.json()
                        message_content = data.get("choices", [{}])[0].get("message", {}).get("content")
                        if message_content:
                            try:
                                # Парсим JSON-ответ
                                parsed_content = await asyncio.to_thread(json.loads, message_content)
                                if isinstance(parsed_content, list):
                                    analysis_result["categorization"] = parsed_content
                                else:
                                    analysis_result["categorization"] = parsed_content.get("categorization", [])
                            except json.JSONDecodeError as je:
                                logger.error(f"Failed to parse JSON response from OpenRouter: {je}. Content: {message_content}")
                                analysis_result["error"] = "Failed to parse LLM response. Content was not valid JSON."
                                analysis_result["raw_response"] = message_content
                        else:
                            analysis_result["error"] = "No content in OpenRouter response message."
                            logger.warning(f"No content in OpenRouter response: {data}")
                    else:
                        error_details = await response.text()
                        logger.error(f"OpenRouter API error (Status {response.status}): {error_details}")
                        analysis_result["error"] = f"OpenRouter API error: {response.status} - {error_details[:200]}"
        except Exception as e:
            logger.exception(f"Unexpected error during OpenRouter domain analysis: {e}")
            analysis_result["error"] = f"An unexpected error occurred: {str(e)}"
        
        return analysis_result

    async def create_custom_agent(self, agent_name: str, system_prompt: str, training_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Создание пользовательского агента с обучением на примерах
        
        Args:
            agent_name: Имя агента
            system_prompt: Системный промпт
            training_data: Обучающие данные (список пар вопрос-ответ)
            
        Returns:
            Результат операции
        """
        if not agent_name or not system_prompt:
            return {"success": False, "error": "Agent name and system prompt cannot be empty"}
        
        if not training_data:
            return {"success": False, "error": "Training data cannot be empty"}
        
        # Создаем нового агента
        if agent_name in self.settings["custom_agents"]:
            return {"success": False, "error": f"Agent '{agent_name}' already exists"}
        
        self.settings["custom_agents"][agent_name] = {
            "system_prompt": system_prompt,
            "training_data": training_data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.save_settings()
        
        return {"success": True, "message": f"Custom agent '{agent_name}' created successfully"}

    async def update_custom_agent(self, agent_name: str, system_prompt: Optional[str] = None, 
                                 training_data: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Обновление пользовательского агента
        
        Args:
            agent_name: Имя агента
            system_prompt: Новый системный промпт (если None, не обновляется)
            training_data: Новые обучающие данные (если None, не обновляются)
            
        Returns:
            Результат операции
        """
        if not agent_name:
            return {"success": False, "error": "Agent name cannot be empty"}
        
        if agent_name not in self.settings["custom_agents"]:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        # Обновляем агента
        if system_prompt:
            self.settings["custom_agents"][agent_name]["system_prompt"] = system_prompt
        
        if training_data:
            self.settings["custom_agents"][agent_name]["training_data"] = training_data
        
        self.settings["custom_agents"][agent_name]["updated_at"] = datetime.now().isoformat()
        
        self.save_settings()
        
        return {"success": True, "message": f"Custom agent '{agent_name}' updated successfully"}

    async def delete_custom_agent(self, agent_name: str) -> Dict[str, Any]:
        """
        Удаление пользовательского агента
        
        Args:
            agent_name: Имя агента
            
        Returns:
            Результат операции
        """
        if not agent_name:
            return {"success": False, "error": "Agent name cannot be empty"}
        
        if agent_name not in self.settings["custom_agents"]:
            return {"success": False, "error": f"Agent '{agent_name}' not found"}
        
        # Удаляем агента
        del self.settings["custom_agents"][agent_name]
        
        self.save_settings()
        
        return {"success": True, "message": f"Custom agent '{agent_name}' deleted successfully"}

    async def use_custom_agent(self, agent_name: str, query: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Использование пользовательского агента для ответа на запрос
        
        Args:
            agent_name: Имя агента
            query: Запрос пользователя
            model: Модель для использования (если None, используется модель по умолчанию)
            
        Returns:
            Результат операции
        """
        if not self.api_key:
            return {"error": "OpenRouter API key not configured."}
        
        if not agent_name:
            return {"error": "Agent name cannot be empty"}
        
        if agent_name not in self.settings["custom_agents"]:
            return {"error": f"Agent '{agent_name}' not found"}
        
        if not query:
            return {"error": "Query cannot be empty"}
        
        # Получаем агента
        agent = self.settings["custom_agents"][agent_name]
        
        # Используем указанную модель или модель по умолчанию
        model_to_use = model or self.model_name
        
        # Получаем настройки запроса
        request_settings = self.settings["request_settings"]
        timeout_seconds = request_settings.get("timeout_seconds", 60)
        max_tokens = request_settings.get("max_tokens", 1000)
        temperature = request_settings.get("temperature", 0.7)
        
        # Формируем сообщения для запроса
        messages = [
            {"role": "system", "content": agent["system_prompt"]}
        ]
        
        # Добавляем обучающие данные
        for item in agent["training_data"]:
            messages.append({"role": "user", "content": item["user"]})
            messages.append({"role": "assistant", "content": item["assistant"]})
        
        # Добавляем текущий запрос
        messages.append({"role": "user", "content": query})
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model_to_use,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        result = {
            "agent": agent_name,
            "query": query,
            "model_used": model_to_use,
            "response": None,
            "error": None
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/chat/completions", 
                                        headers=headers, 
                                        json=payload, 
                                        timeout=timeout_seconds) as response:
                    if response.status == 200:
                        data = await response.json()
                        message_content = data.get("choices", [{}])[0].get("message", {}).get("content")
                        if message_content:
                            result["response"] = message_content
                        else:
                            result["error"] = "No content in OpenRouter response message."
                            logger.warning(f"No content in OpenRouter response: {data}")
                    else:
                        error_details = await response.text()
                        logger.error(f"OpenRouter API error (Status {response.status}): {error_details}")
                        result["error"] = f"OpenRouter API error: {response.status} - {error_details[:200]}"
        except Exception as e:
            logger.exception(f"Unexpected error during custom agent query: {e}")
            result["error"] = f"An unexpected error occurred: {str(e)}"
        
        return result

    async def get_settings(self) -> Dict[str, Any]:
        """
        Получение текущих настроек
        
        Returns:
            Текущие настройки
        """
        # Скрываем API ключ в ответе
        settings_copy = self.settings.copy()
        if "api_key" in settings_copy:
            settings_copy["api_key"] = "***" if settings_copy["api_key"] else None
        
        return settings_copy

    async def update_request_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновление настроек запросов
        
        Args:
            settings: Новые настройки
            
        Returns:
            Результат операции
        """
        if not settings:
            return {"success": False, "error": "Settings cannot be empty"}
        
        # Проверяем валидность настроек
        valid_keys = ["max_tokens", "temperature", "timeout_seconds", "max_content_length"]
        invalid_keys = [k for k in settings.keys() if k not in valid_keys]
        
        if invalid_keys:
            return {"success": False, "error": f"Invalid settings keys: {invalid_keys}. Valid keys: {valid_keys}"}
        
        # Обновляем настройки
        for k, v in settings.items():
            self.settings["request_settings"][k] = v
        
        self.save_settings()
        
        return {"success": True, "message": "Request settings updated successfully"}
