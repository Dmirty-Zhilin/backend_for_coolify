import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WaybackService:
    """
    Сервис для работы с Wayback Machine API.
    Адаптирован для работы с waybackpy версии 3.0.6.
    """
    
    def __init__(self, user_agent: str = None):
        """
        Инициализация сервиса.
        
        Args:
            user_agent: User-Agent для запросов к Wayback Machine API
        """
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        
        # Проверка наличия и версии библиотеки waybackpy
        try:
            import waybackpy
            self.waybackpy_available = True
            self.waybackpy = waybackpy
            logger.info(f"waybackpy version {waybackpy.__version__} is available")
        except ImportError:
            logger.warning("waybackpy library is not installed. Using fallback implementation.")
            self.waybackpy_available = False
            self.waybackpy = None
    
    async def analyze_domain(self, domain: str, match_type: str = "domain", collapse: str = "timestamp", limit: int = 1000) -> Dict[str, Any]:
        """
        Анализ домена с использованием Wayback Machine API.
        
        Args:
            domain: Домен для анализа
            match_type: Тип совпадения (domain, prefix, exact)
            collapse: Параметр группировки снимков (timestamp, digest)
            limit: Максимальное количество снимков для анализа
            
        Returns:
            Dict: Результаты анализа
        """
        if not self.waybackpy_available:
            return {
                "domain": domain,
                "error": "waybackpy library is not available"
            }
        
        try:
            # Формирование URL для запроса
            url = f"http://{domain}"
            
            # Создание экземпляра CDX API
            cdx_api = self.waybackpy.WaybackMachineCDXServerAPI(
                url=url,
                user_agent=self.user_agent
            )
            
            # Получение списка снимков
            try:
                snapshots = list(cdx_api.snapshots())
                total_snapshots = len(snapshots)
            except Exception as e:
                logger.error(f"Error getting snapshots: {str(e)}")
                return {
                    "domain": domain,
                    "error": f"Failed to get snapshots: {str(e)}",
                    "availability_api_response": {"error": str(e)}
                }
            
            # Если снимков нет, возвращаем пустой результат
            if total_snapshots == 0:
                return {
                    "domain": domain,
                    "first_snapshot_date": None,
                    "last_snapshot_date": None,
                    "total_snapshots": 0,
                    "availability_api_response": {"snapshots": []},
                    "oldest_snapshot_url": None,
                    "newest_snapshot_url": None
                }
            
            # Получение первого и последнего снимка
            oldest_snapshot = snapshots[0] if snapshots else None
            newest_snapshot = snapshots[-1] if snapshots else None
            
            # Формирование URL для снимков
            oldest_snapshot_url = f"https://web.archive.org/web/{oldest_snapshot.timestamp}/{oldest_snapshot.original}" if oldest_snapshot else None
            newest_snapshot_url = f"https://web.archive.org/web/{newest_snapshot.timestamp}/{newest_snapshot.original}" if newest_snapshot else None
            
            # Анализ временных интервалов между снимками
            timestamps = []
            for snapshot in snapshots:
                try:
                    timestamp = snapshot.timestamp
                    if timestamp:
                        timestamps.append(datetime.strptime(timestamp, "%Y%m%d%H%M%S"))
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Error parsing timestamp: {str(e)}")
            
            # Сортировка временных меток
            timestamps.sort()
            
            # Расчет интервалов между снимками
            intervals = []
            for i in range(1, len(timestamps)):
                interval = (timestamps[i] - timestamps[i-1]).total_seconds() / (60 * 60 * 24)  # в днях
                intervals.append(interval)
            
            # Расчет статистики
            avg_interval = sum(intervals) / len(intervals) if intervals else 0
            max_interval = max(intervals) if intervals else 0
            
            # Расчет количества лет между первым и последним снимком
            years_covered = 0
            if timestamps and len(timestamps) > 1:
                years_covered = (timestamps[-1] - timestamps[0]).total_seconds() / (60 * 60 * 24 * 365.25)
            
            # Формирование результата
            result = {
                "domain": domain,
                "first_snapshot_date": timestamps[0].isoformat() if timestamps else None,
                "last_snapshot_date": timestamps[-1].isoformat() if timestamps else None,
                "total_snapshots": total_snapshots,
                "years_covered": years_covered,
                "avg_interval_days": avg_interval,
                "max_gap_days": max_interval,
                "oldest_snapshot_url": oldest_snapshot_url,
                "newest_snapshot_url": newest_snapshot_url,
                "is_long_live": False  # Будет установлено позже
            }
            
            # Определение "long-live" доменов
            result["is_long_live"] = (
                total_snapshots >= 5 and
                years_covered >= 3 and
                avg_interval < 90 and
                max_interval < 180
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing domain {domain}: {str(e)}")
            return {
                "domain": domain,
                "error": f"An unexpected error occurred: {str(e)}"
            }
    
    async def analyze_domains(self, domains: List[str], match_type: str = "domain", collapse: str = "timestamp", limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Анализ списка доменов с использованием Wayback Machine API.
        
        Args:
            domains: Список доменов для анализа
            match_type: Тип совпадения (domain, prefix, exact)
            collapse: Параметр группировки снимков (timestamp, digest)
            limit: Максимальное количество снимков для анализа
            
        Returns:
            List[Dict]: Результаты анализа для каждого домена
        """
        tasks = []
        for domain in domains:
            task = asyncio.create_task(self.analyze_domain(domain, match_type, collapse, limit))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        return results
