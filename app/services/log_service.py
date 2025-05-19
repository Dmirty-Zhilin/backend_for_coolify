import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from io import BytesIO
import json

# Настройка логирования
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

class LogService:
    def __init__(self, logs_dir: str = "logs"):
        """Инициализация сервиса логов"""
        self.logs_dir = logs_dir
        
        # Создаем директорию для логов, если она не существует
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Путь к файлу логов
        self.log_file = os.path.join(self.logs_dir, "app.log")
        
        # Настройка файлового логгера
        self.setup_file_logger()
    
    def setup_file_logger(self):
        """Настройка файлового логгера"""
        # Создаем обработчик для записи в файл
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.INFO)
        
        # Формат логов
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Добавляем обработчик к корневому логгеру
        root_logger = logging.getLogger()
        root_logger.addHandler(file_handler)
        
        logger.info(f"File logger set up. Log file: {self.log_file}")
    
    async def get_logs(self, limit: int = 100, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получение логов с возможностью фильтрации по уровню"""
        if not os.path.exists(self.log_file):
            logger.warning(f"Log file not found: {self.log_file}")
            return []
        
        try:
            with open(self.log_file, "r") as f:
                lines = f.readlines()
            
            # Парсинг логов
            logs = []
            for line in lines[-limit:]:  # Берем только последние limit строк
                try:
                    # Парсим строку лога
                    parts = line.strip().split(" - ", 3)
                    if len(parts) >= 4:
                        timestamp, name, log_level, message = parts
                        
                        # Фильтрация по уровню, если указан
                        if level and log_level != level:
                            continue
                        
                        logs.append({
                            "timestamp": timestamp,
                            "name": name,
                            "level": log_level,
                            "message": message
                        })
                except Exception as e:
                    logger.error(f"Error parsing log line: {e}")
                    continue
            
            return logs
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            return []
    
    async def clear_logs(self) -> Dict[str, Any]:
        """Очистка файла логов"""
        if not os.path.exists(self.log_file):
            logger.warning(f"Log file not found: {self.log_file}")
            return {"success": False, "error": "Log file not found"}
        
        try:
            # Очищаем файл логов
            with open(self.log_file, "w") as f:
                f.write("")
            
            # Записываем сообщение о очистке
            logger.info("Logs cleared")
            
            return {"success": True, "message": "Logs cleared successfully"}
        except Exception as e:
            logger.error(f"Error clearing logs: {e}")
            return {"success": False, "error": str(e)}
    
    async def download_logs(self, format: str = "txt") -> Optional[BytesIO]:
        """Скачивание логов в указанном формате"""
        if not os.path.exists(self.log_file):
            logger.error(f"Log file not found: {self.log_file}")
            return None
        
        try:
            if format == "txt":
                # Просто читаем файл логов
                with open(self.log_file, "rb") as f:
                    file_data = BytesIO(f.read())
                    file_data.seek(0)
                    return file_data
            elif format == "json":
                # Преобразуем логи в JSON
                logs = await self.get_logs(limit=10000)  # Большой лимит для получения всех логов
                json_data = json.dumps(logs, indent=2)
                file_data = BytesIO(json_data.encode("utf-8"))
                file_data.seek(0)
                return file_data
            else:
                logger.error(f"Unknown format: {format}")
                return None
        except Exception as e:
            logger.error(f"Error downloading logs: {e}")
            return None
    
    def log(self, level: str, message: str) -> Dict[str, Any]:
        """Запись лога с указанным уровнем"""
        try:
            if level == "INFO":
                logger.info(message)
            elif level == "WARNING":
                logger.warning(message)
            elif level == "ERROR":
                logger.error(message)
            elif level == "DEBUG":
                logger.debug(message)
            else:
                logger.warning(f"Unknown log level: {level}. Using INFO.")
                logger.info(message)
            
            return {"success": True, "message": "Log recorded successfully"}
        except Exception as e:
            logger.error(f"Error recording log: {e}")
            return {"success": False, "error": str(e)}
