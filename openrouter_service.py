import os
import logging
import requests
from typing import Dict, List, Any, Optional

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenRouterService:
    """
    Сервис для работы с OpenRouter API.
    Поддерживает тематический анализ и создание ИИ агентов.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализация сервиса.
        
        Args:
            api_key: API ключ для доступа к OpenRouter
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"
        self.available = self.api_key is not None and len(self.api_key) > 0
        
        if not self.available:
            logger.warning("OpenRouter API key is not set. Thematic analysis will not work.")
    
    def analyze_domain_theme(self, domain: str, content: str) -> Dict[str, Any]:
        """
        Анализ тематики домена с использованием OpenRouter.
        
        Args:
            domain: Домен для анализа
            content: Содержимое домена для анализа
            
        Returns:
            Dict: Результаты анализа тематики
        """
        if not self.available:
            return {
                "domain": domain,
                "error": "OpenRouter API key not configured. Skipping thematic analysis."
            }
        
        try:
            # Формирование запроса к OpenRouter
            prompt = f"""
            Analyze the following domain and its content to determine its thematic category:
            
            Domain: {domain}
            Content: {content}
            
            Please provide:
            1. Main thematic category (e.g., Technology, Health, Finance, etc.)
            2. Subcategories (if applicable)
            3. Potential commercial value (High, Medium, Low)
            4. Target audience
            5. Potential use cases for this domain
            
            Format your response as JSON with the following structure:
            {{
                "main_category": "string",
                "subcategories": ["string", "string"],
                "commercial_value": "string",
                "target_audience": "string",
                "use_cases": ["string", "string"]
            }}
            """
            
            # Отправка запроса к OpenRouter
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai/gpt-4-turbo",
                    "messages": [
                        {"role": "system", "content": "You are a domain analysis expert."},
                        {"role": "user", "content": prompt}
                    ]
                }
            )
            
            # Обработка ответа
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                
                # Попытка парсинга JSON из ответа
                try:
                    import json
                    analysis = json.loads(content)
                    analysis["domain"] = domain
                    return analysis
                except Exception as e:
                    logger.error(f"Error parsing OpenRouter response: {str(e)}")
                    return {
                        "domain": domain,
                        "error": f"Failed to parse OpenRouter response: {str(e)}",
                        "raw_response": content
                    }
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "domain": domain,
                    "error": f"OpenRouter API error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error analyzing domain theme for {domain}: {str(e)}")
            return {
                "domain": domain,
                "error": f"An unexpected error occurred during thematic analysis: {str(e)}"
            }
    
    def create_ai_agent(self, name: str, description: str, prompt_template: str, model: str = "openai/gpt-4-turbo") -> Dict[str, Any]:
        """
        Создание ИИ агента с произвольным промптом и задачей.
        
        Args:
            name: Имя агента
            description: Описание агента
            prompt_template: Шаблон промпта для агента
            model: Модель для использования (по умолчанию gpt-4-turbo)
            
        Returns:
            Dict: Информация о созданном агенте
        """
        if not self.available:
            return {
                "error": "OpenRouter API key not configured. Cannot create AI agent."
            }
        
        try:
            # Формирование запроса к OpenRouter для создания агента
            response = requests.post(
                f"{self.base_url}/agents",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "name": name,
                    "description": description,
                    "model": model,
                    "prompt_template": prompt_template,
                    "tools": []  # Можно добавить инструменты, если необходимо
                }
            )
            
            # Обработка ответа
            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "agent": response.json()
                }
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"OpenRouter API error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error creating AI agent: {str(e)}")
            return {
                "success": False,
                "error": f"An unexpected error occurred while creating AI agent: {str(e)}"
            }
    
    def save_trained_model(self, model_name: str, training_data: List[Dict[str, str]], base_model: str = "openai/gpt-3.5-turbo") -> Dict[str, Any]:
        """
        Сохранение обученной модели.
        
        Args:
            model_name: Имя модели
            training_data: Данные для обучения модели (список пар вопрос-ответ)
            base_model: Базовая модель для дообучения
            
        Returns:
            Dict: Информация о сохраненной модели
        """
        if not self.available:
            return {
                "error": "OpenRouter API key not configured. Cannot save trained model."
            }
        
        try:
            # Формирование запроса к OpenRouter для сохранения модели
            response = requests.post(
                f"{self.base_url}/models/finetune",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "name": model_name,
                    "base_model": base_model,
                    "training_data": training_data
                }
            )
            
            # Обработка ответа
            if response.status_code in [200, 201, 202]:
                return {
                    "success": True,
                    "model": response.json()
                }
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"OpenRouter API error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error saving trained model: {str(e)}")
            return {
                "success": False,
                "error": f"An unexpected error occurred while saving trained model: {str(e)}"
            }
    
    def list_saved_models(self) -> Dict[str, Any]:
        """
        Получение списка сохраненных моделей.
        
        Returns:
            Dict: Список сохраненных моделей
        """
        if not self.available:
            return {
                "error": "OpenRouter API key not configured. Cannot list saved models."
            }
        
        try:
            # Формирование запроса к OpenRouter для получения списка моделей
            response = requests.get(
                f"{self.base_url}/models",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            # Обработка ответа
            if response.status_code == 200:
                return {
                    "success": True,
                    "models": response.json()
                }
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"OpenRouter API error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"Error listing saved models: {str(e)}")
            return {
                "success": False,
                "error": f"An unexpected error occurred while listing saved models: {str(e)}"
            }
