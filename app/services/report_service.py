import asyncio
import logging
import statistics
import json
import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import aiohttp
from io import BytesIO

from app.services.wayback_service import WaybackService

# Настройка логирования
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

# Константы из way2_fixed.py
CDX_API = "https://web.archive.org/cdx/search/cdx"
AVAIL_API = "https://archive.org/wayback/available"
TIMEMAP_URL = "http://web.archive.org/web/timemap/link/{url}"
REQUEST_TIMEOUT = 30  # секунд
RETRY_DELAY = 2  # секунд
RETRY_COUNT = 3

class ReportService:
    def __init__(self, reports_dir: str = "reports"):
        """Инициализация сервиса отчетов"""
        self.reports_dir = reports_dir
        self.wayback_service = WaybackService()
        
        # Создаем директорию для отчетов, если она не существует
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Пути к файлам отчетов
        self.drop_report_csv = os.path.join(self.reports_dir, "drop_report.csv")
        self.drop_report_excel = os.path.join(self.reports_dir, "drop_report.xlsx")
        self.drop_report_long_live_csv = os.path.join(self.reports_dir, "drop_report_long_live.csv")
        self.drop_report_long_live_excel = os.path.join(self.reports_dir, "drop_report_long_live.xlsx")

    async def safe_request(self, session: aiohttp.ClientSession, method: str, url: str, **kwargs):
        """Универсальный безопасный запрос с ретраями."""
        for attempt in range(1, RETRY_COUNT + 1):
            try:
                async with session.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs) as resp:
                    resp.raise_for_status()  # Проверка на HTTP ошибки (4xx, 5xx)
                    if kwargs.get("params", {}).get("output") == "json" or "application/json" in resp.headers.get("Content-Type", ""):
                        # Проверка, что ответ действительно JSON перед парсингом
                        text_content = await resp.text()  # Сначала читаем как текст
                        if not text_content.strip():  # Если ответ пустой
                            logger.warning(f"[{attempt}/{RETRY_COUNT}] Empty JSON response from {url} with params {kwargs.get('params')}")
                            return None
                        try:
                            return json.loads(text_content)  # Затем парсим JSON
                        except json.JSONDecodeError as je:
                            logger.error(f"[{attempt}/{RETRY_COUNT}] JSON decode error for {url} {kwargs.get('params')}: {je}. Response text: {text_content[:200]}")
                            if attempt == RETRY_COUNT:
                                return None
                    else:
                        return await resp.text()
            except aiohttp.ClientResponseError as e:
                logger.warning(f"[{attempt}/{RETRY_COUNT}] HTTP error {e.status} for {url} {kwargs.get('params')}: {e.message}")
                if e.status == 429:  # Too Many Requests
                    logger.info(f"Rate limit hit for {url}. Sleeping for {RETRY_DELAY * attempt * 2} seconds.")
                    await asyncio.sleep(RETRY_DELAY * attempt * 2)  # Увеличенная задержка для 429
                elif e.status >= 500:  # Server errors
                    await asyncio.sleep(RETRY_DELAY * attempt)
                elif attempt == RETRY_COUNT:
                    logger.error(f"Failed to fetch {url} after {RETRY_COUNT} attempts due to HTTP {e.status}.")
                    return None
            except asyncio.TimeoutError:
                logger.warning(f"[{attempt}/{RETRY_COUNT}] Timeout error for {url} {kwargs.get('params')}")
                if attempt == RETRY_COUNT:
                    logger.error(f"Failed to fetch {url} after {RETRY_COUNT} attempts due to timeout.")
                    return None
            except aiohttp.ClientError as e:  # Другие ошибки клиента
                logger.warning(f"[{attempt}/{RETRY_COUNT}] Client error for {url} {kwargs.get('params')}: {e}")
                if attempt == RETRY_COUNT:
                    logger.error(f"Failed to fetch {url} after {RETRY_COUNT} attempts due to client error.")
                    return None
            except Exception as e:
                logger.error(f"[{attempt}/{RETRY_COUNT}] Unexpected error for {url} {kwargs.get('params')}: {e}")
                if attempt == RETRY_COUNT:
                    return None
            if attempt < RETRY_COUNT:
                await asyncio.sleep(RETRY_DELAY * attempt)  # Экспоненциальная задержка
        return None

    async def analyze_domain(self, domain: str, session: aiohttp.ClientSession, 
                            match_type: str = "prefix", 
                            collapse: Optional[str] = None, 
                            limit: int = 1000) -> Dict[str, Any]:
        """Собираем метрики по одному домену."""
        info = {"domain": domain}  # Инициализация с доменом
        start = datetime.utcnow()

        # Availability API
        avail_params = {"url": domain}
        avail = await self.safe_request(session, "GET", AVAIL_API, params=avail_params)
        if avail and isinstance(avail, dict) and avail.get("archived_snapshots", {}).get("closest"):
            closest = avail["archived_snapshots"]["closest"]
            info["has_snapshot"] = bool(closest.get("available"))
            info["availability_ts"] = closest.get("timestamp")
        else:
            logger.warning(f"Could not retrieve availability for {domain}. Response: {avail}")
            info["has_snapshot"] = False
            info["availability_ts"] = None

        # CDX API
        records = []
        offset = 0
        base_cdx_params = {
            "url": domain,
            "matchType": match_type,
            "output": "json",
            "fl": "timestamp,original,digest",
            "limit": limit
        }
        if collapse:
            base_cdx_params["collapse"] = collapse

        while True:
            cdx_params = {**base_cdx_params, "offset": offset}
            batch = await self.safe_request(session, "GET", CDX_API, params=cdx_params)
            
            if not batch or not isinstance(batch, list) or len(batch) < 1:
                if isinstance(batch, list) and len(batch) == 1 and batch[0] == ['timestamp', 'original', 'digest']:
                    logger.info(f"CDX API returned only headers for {domain} with offset {offset}. Assuming no more data.")
                elif not batch:
                    logger.warning(f"CDX API returned empty or invalid batch for {domain} with offset {offset}. Batch: {batch}")
                break

            # Обработка данных из batch
            current_records = []
            if isinstance(batch[0], list):  # Заголовки присутствуют
                if len(batch) < 2:  # Только заголовки, нет данных
                    logger.info(f"CDX API returned only headers for {domain} with offset {offset}. No data rows.")
                    break
                cols = batch[0]
                for row in batch[1:]:
                    if isinstance(row, list) and len(row) == len(cols):
                        records.append(dict(zip(cols, row)))
                        current_records.append(dict(zip(cols, row)))
                    else:
                        logger.warning(f"Skipping malformed row in CDX batch for {domain}: {row}")
            elif isinstance(batch[0], dict):  # Данные без заголовков
                cols = list(batch[0].keys())
                for item in batch:
                    if isinstance(item, dict):
                        records.append(item)
                        current_records.append(item)
                    else:
                        logger.warning(f"Skipping malformed item in CDX batch for {domain}: {item}")
            else:
                logger.warning(f"Unexpected CDX batch format for {domain} with offset {offset}. Batch: {batch}")
                break
            
            if len(current_records) < limit:
                break
            offset += limit
            if offset > 50000 and limit > 0:
                logger.warning(f"Reached max offset (50000) for {domain}. Stopping CDX pagination.")
                break

        info["total_snapshots"] = len(records)

        # Timemap count
        tm_text = await self.safe_request(session, "GET", TIMEMAP_URL.format(url=domain))
        info["timemap_count"] = tm_text.count("web/") if tm_text and isinstance(tm_text, str) else 0

        # Метрики снимков
        if records:
            try:
                times = sorted([r["timestamp"] for r in records if "timestamp" in r and r["timestamp"] is not None])
                dates = [datetime.strptime(ts, "%Y%m%d%H%M%S") for ts in times if len(ts) == 14]
                if dates:
                    info["first_snapshot"] = dates[0]
                    info["last_snapshot"] = dates[-1]
                    gaps = [(dates[i] - dates[i-1]).days for i in range(1, len(dates))]
                    info["avg_interval_days"] = round(statistics.mean(gaps), 2) if gaps else 0
                    info["max_gap_days"] = max(gaps) if gaps else 0
                    years = {d.year for d in dates}
                    info["years_covered"] = len(years)
                    info["snapshots_per_year"] = json.dumps({y: sum(1 for d in dates if d.year==y) for y in sorted(list(years))})
                    info["unique_versions"] = len({r["digest"] for r in records if "digest" in r})
                else:
                    logger.warning(f"No valid dates found for {domain} despite having records. Timestamps: {times}")
                    for k in ("first_snapshot", "last_snapshot", "avg_interval_days",
                            "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                        info[k] = None
            except Exception as e:
                logger.error(f"Error processing snapshot metrics for {domain}: {e}. Records: {records[:5]}")
                for k in ("first_snapshot", "last_snapshot", "avg_interval_days",
                        "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                    info[k] = None
        else:
            for k in ("first_snapshot", "last_snapshot", "avg_interval_days",
                    "max_gap_days", "years_covered", "snapshots_per_year", "unique_versions"):
                info[k] = None

        # Флаги
        total_snapshots_val = info.get("total_snapshots", 0)
        max_gap_days_val = info.get("max_gap_days")
        avg_interval_days_val = info.get("avg_interval_days")

        info["is_good"] = (total_snapshots_val >= 1) and (max_gap_days_val is not None and max_gap_days_val < 365)
        info["recommended"] = (total_snapshots_val >= 200) and (avg_interval_days_val is not None and avg_interval_days_val < 30)

        info["analysis_time_sec"] = round((datetime.utcnow() - start).total_seconds(), 2)
        return info

    async def generate_report(self, domains: List[str], 
                             match_type: str = "prefix", 
                             collapse: Optional[str] = None, 
                             limit: int = 1000,
                             concurrency: int = 10) -> Dict[str, Any]:
        """Генерация отчета для списка доменов."""
        if not domains:
            logger.warning("No domains provided for analysis.")
            return {"error": "No domains provided", "domains_count": 0, "success": False}

        # Создаем семафор для ограничения одновременных запросов
        semaphore = asyncio.Semaphore(concurrency)
        conn = aiohttp.TCPConnector(limit_per_host=concurrency)
        
        async def analyze_domain_with_semaphore(domain: str):
            """Обертка для analyze_domain с использованием семафора."""
            async with semaphore:
                return await self.analyze_domain(domain, session, match_type, collapse, limit)
        
        results = []
        start_time = datetime.utcnow()
        
        async with aiohttp.ClientSession(connector=conn) as session:
            tasks = [asyncio.create_task(analyze_domain_with_semaphore(d)) for d in domains]
            
            for fut in asyncio.as_completed(tasks):
                try:
                    result = await fut
                    if result:
                        results.append(result)
                    else:
                        logger.error("Task for a domain completed but returned None.")
                except Exception as e:
                    logger.error(f"Error processing a domain task: {e}")
        
        if not results:
            logger.warning("No results were gathered from domain analysis.")
            return {"error": "No results gathered", "domains_count": len(domains), "success": False}
        
        # Создаем DataFrame из результатов
        df = pd.DataFrame(results)
        
        # Фильтрация для long-live отчета
        required_cols_long_live = ["total_snapshots", "years_covered", "avg_interval_days", "max_gap_days", "timemap_count"]
        
        if all(col in df.columns for col in required_cols_long_live):
            # Преобразование и заполнение значений для корректной фильтрации
            df_filtered = df.copy()
            df_filtered["total_snapshots"] = pd.to_numeric(df_filtered["total_snapshots"], errors='coerce').fillna(0)
            df_filtered["years_covered"] = pd.to_numeric(df_filtered["years_covered"], errors='coerce').fillna(0)
            df_filtered["avg_interval_days"] = pd.to_numeric(df_filtered["avg_interval_days"], errors='coerce').fillna(float('inf'))
            df_filtered["max_gap_days"] = pd.to_numeric(df_filtered["max_gap_days"], errors='coerce').fillna(float('inf'))
            df_filtered["timemap_count"] = pd.to_numeric(df_filtered["timemap_count"], errors='coerce').fillna(0)
            
            # Применяем фильтры для long-live отчета
            df_long = df_filtered[
                (df_filtered.total_snapshots >= 5) &
                (df_filtered.years_covered >= 3) &
                (df_filtered.avg_interval_days < 90) &
                (df_filtered.max_gap_days < 180) &
                (df_filtered.timemap_count > 200)
            ]
            
            # Сохраняем отчеты
            try:
                # Преобразование столбцов с датами перед сохранением
                for col_name in ["first_snapshot", "last_snapshot"]:
                    if col_name in df.columns:
                        df[col_name] = pd.to_datetime(df[col_name], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').replace('NaT', '')
                
                # Замена всех NaN на пустые строки
                df = df.fillna('')
                df_long = df_long.fillna('')
                
                # Сохраняем основной отчет
                df.to_csv(self.drop_report_csv, index=False)
                df.to_excel(self.drop_report_excel, index=False, engine='openpyxl')
                
                # Сохраняем long-live отчет
                if not df_long.empty:
                    df_long.to_csv(self.drop_report_long_live_csv, index=False)
                    df_long.to_excel(self.drop_report_long_live_excel, index=False, engine='openpyxl')
                    
                    # Форматирование Excel-отчетов можно добавить здесь
                    # self.format_excel(self.drop_report_excel)
                    # self.format_excel(self.drop_report_long_live_excel)
                    
                    logger.info(f"Reports saved successfully. Main report: {len(df)} domains, Long-live report: {len(df_long)} domains.")
                    return {
                        "success": True,
                        "domains_count": len(domains),
                        "analyzed_count": len(df),
                        "long_live_count": len(df_long),
                        "execution_time_sec": round((datetime.utcnow() - start_time).total_seconds(), 2),
                        "report_paths": {
                            "drop_report_csv": self.drop_report_csv,
                            "drop_report_excel": self.drop_report_excel,
                            "drop_report_long_live_csv": self.drop_report_long_live_csv,
                            "drop_report_long_live_excel": self.drop_report_long_live_excel
                        }
                    }
                else:
                    logger.info(f"Main report saved with {len(df)} domains. No domains met long-live criteria.")
                    return {
                        "success": True,
                        "domains_count": len(domains),
                        "analyzed_count": len(df),
                        "long_live_count": 0,
                        "execution_time_sec": round((datetime.utcnow() - start_time).total_seconds(), 2),
                        "report_paths": {
                            "drop_report_csv": self.drop_report_csv,
                            "drop_report_excel": self.drop_report_excel
                        }
                    }
            except Exception as e:
                logger.error(f"Error saving reports: {e}")
                return {"error": f"Error saving reports: {str(e)}", "domains_count": len(domains), "success": False}
        else:
            missing_cols = [col for col in required_cols_long_live if col not in df.columns]
            logger.warning(f"Missing columns for long-live report: {missing_cols}")
            return {"error": f"Missing columns for long-live report: {missing_cols}", "domains_count": len(domains), "success": False}

    async def get_report(self, report_type: str = "drop_report") -> Dict[str, Any]:
        """Получение существующего отчета."""
        if report_type == "drop_report":
            csv_path = self.drop_report_csv
            excel_path = self.drop_report_excel
        elif report_type == "drop_report_long_live":
            csv_path = self.drop_report_long_live_csv
            excel_path = self.drop_report_long_live_excel
        else:
            return {"error": f"Unknown report type: {report_type}", "success": False}
        
        if not os.path.exists(csv_path) and not os.path.exists(excel_path):
            return {"error": f"Report {report_type} not found", "success": False}
        
        try:
            # Читаем CSV-отчет, если он существует
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                return {
                    "success": True,
                    "report_type": report_type,
                    "domains_count": len(df),
                    "report_data": df.to_dict(orient="records"),
                    "report_paths": {
                        "csv": csv_path,
                        "excel": excel_path if os.path.exists(excel_path) else None
                    }
                }
            # Если CSV не существует, но Excel существует
            elif os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                return {
                    "success": True,
                    "report_type": report_type,
                    "domains_count": len(df),
                    "report_data": df.to_dict(orient="records"),
                    "report_paths": {
                        "csv": None,
                        "excel": excel_path
                    }
                }
        except Exception as e:
            logger.error(f"Error reading report {report_type}: {e}")
            return {"error": f"Error reading report: {str(e)}", "success": False}

    async def download_report(self, report_type: str = "drop_report", format: str = "csv") -> Optional[BytesIO]:
        """Скачивание отчета в указанном формате."""
        if report_type == "drop_report":
            if format == "csv":
                path = self.drop_report_csv
            elif format == "excel":
                path = self.drop_report_excel
            else:
                logger.error(f"Unknown format: {format}")
                return None
        elif report_type == "drop_report_long_live":
            if format == "csv":
                path = self.drop_report_long_live_csv
            elif format == "excel":
                path = self.drop_report_long_live_excel
            else:
                logger.error(f"Unknown format: {format}")
                return None
        else:
            logger.error(f"Unknown report type: {report_type}")
            return None
        
        if not os.path.exists(path):
            logger.error(f"Report file not found: {path}")
            return None
        
        try:
            # Читаем файл в BytesIO для передачи через API
            with open(path, "rb") as f:
                file_data = BytesIO(f.read())
                file_data.seek(0)
                return file_data
        except Exception as e:
            logger.error(f"Error reading report file {path}: {e}")
            return None
