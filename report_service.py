import os
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
import io

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReportService:
    """
    Сервис для генерации отчетов по результатам анализа доменов.
    """
    
    def __init__(self, output_dir: str = None):
        """
        Инициализация сервиса.
        
        Args:
            output_dir: Директория для сохранения отчетов
        """
        self.output_dir = output_dir or os.path.join(os.getcwd(), "reports")
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_excel_report(self, domains_data: List[Dict[str, Any]], include_thematic: bool = False) -> str:
        """
        Генерация отчета в формате Excel.
        
        Args:
            domains_data: Данные о доменах
            include_thematic: Включать ли данные тематического анализа
            
        Returns:
            str: Путь к сгенерированному отчету
        """
        try:
            # Создание DataFrame из данных о доменах
            df = pd.DataFrame(domains_data)
            
            # Определение основных колонок для отчета
            columns = [
                "domain", "total_snapshots", "years_covered", 
                "avg_interval_days", "max_gap_days", "is_long_live",
                "first_snapshot_date", "last_snapshot_date",
                "oldest_snapshot_url", "newest_snapshot_url"
            ]
            
            # Добавление колонок тематического анализа, если требуется
            if include_thematic:
                thematic_columns = [
                    "main_category", "subcategories", "commercial_value",
                    "target_audience", "use_cases"
                ]
                for col in thematic_columns:
                    if col in df.columns:
                        columns.append(col)
            
            # Фильтрация колонок
            df_filtered = df[columns] if all(col in df.columns for col in columns) else df
            
            # Генерация имени файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"drop_report_{timestamp}.xlsx"
            filepath = os.path.join(self.output_dir, filename)
            
            # Создание Excel-писателя
            writer = pd.ExcelWriter(filepath, engine='openpyxl')
            
            # Запись всех доменов
            df_filtered.to_excel(writer, sheet_name='All Domains', index=False)
            
            # Запись только "long-live" доменов, если они есть
            if "is_long_live" in df_filtered.columns:
                long_live_df = df_filtered[df_filtered["is_long_live"] == True]
                if not long_live_df.empty:
                    long_live_df.to_excel(writer, sheet_name='Long Live Domains', index=False)
            
            # Сохранение файла
            writer.close()
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating Excel report: {str(e)}")
            raise
    
    def generate_csv_report(self, domains_data: List[Dict[str, Any]], include_thematic: bool = False) -> str:
        """
        Генерация отчета в формате CSV.
        
        Args:
            domains_data: Данные о доменах
            include_thematic: Включать ли данные тематического анализа
            
        Returns:
            str: Путь к сгенерированному отчету
        """
        try:
            # Создание DataFrame из данных о доменах
            df = pd.DataFrame(domains_data)
            
            # Определение основных колонок для отчета
            columns = [
                "domain", "total_snapshots", "years_covered", 
                "avg_interval_days", "max_gap_days", "is_long_live",
                "first_snapshot_date", "last_snapshot_date"
            ]
            
            # Добавление колонок тематического анализа, если требуется
            if include_thematic:
                thematic_columns = [
                    "main_category", "subcategories", "commercial_value",
                    "target_audience", "use_cases"
                ]
                for col in thematic_columns:
                    if col in df.columns:
                        columns.append(col)
            
            # Фильтрация колонок
            df_filtered = df[columns] if all(col in df.columns for col in columns) else df
            
            # Генерация имени файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"drop_report_{timestamp}.csv"
            filepath = os.path.join(self.output_dir, filename)
            
            # Сохранение в CSV
            df_filtered.to_csv(filepath, index=False)
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error generating CSV report: {str(e)}")
            raise
    
    def generate_excel_bytes(self, domains_data: List[Dict[str, Any]], include_thematic: bool = False) -> bytes:
        """
        Генерация отчета в формате Excel и возврат в виде байтов.
        
        Args:
            domains_data: Данные о доменах
            include_thematic: Включать ли данные тематического анализа
            
        Returns:
            bytes: Отчет в виде байтов
        """
        try:
            # Создание DataFrame из данных о доменах
            df = pd.DataFrame(domains_data)
            
            # Определение основных колонок для отчета
            columns = [
                "domain", "total_snapshots", "years_covered", 
                "avg_interval_days", "max_gap_days", "is_long_live",
                "first_snapshot_date", "last_snapshot_date",
                "oldest_snapshot_url", "newest_snapshot_url"
            ]
            
            # Добавление колонок тематического анализа, если требуется
            if include_thematic:
                thematic_columns = [
                    "main_category", "subcategories", "commercial_value",
                    "target_audience", "use_cases"
                ]
                for col in thematic_columns:
                    if col in df.columns:
                        columns.append(col)
            
            # Фильтрация колонок
            df_filtered = df[columns] if all(col in df.columns for col in columns) else df
            
            # Создание буфера в памяти
            output = io.BytesIO()
            
            # Создание Excel-писателя
            writer = pd.ExcelWriter(output, engine='openpyxl')
            
            # Запись всех доменов
            df_filtered.to_excel(writer, sheet_name='All Domains', index=False)
            
            # Запись только "long-live" доменов, если они есть
            if "is_long_live" in df_filtered.columns:
                long_live_df = df_filtered[df_filtered["is_long_live"] == True]
                if not long_live_df.empty:
                    long_live_df.to_excel(writer, sheet_name='Long Live Domains', index=False)
            
            # Сохранение в буфер
            writer.close()
            
            # Получение байтов из буфера
            excel_data = output.getvalue()
            output.close()
            
            return excel_data
            
        except Exception as e:
            logger.error(f"Error generating Excel bytes: {str(e)}")
            raise
    
    def generate_csv_bytes(self, domains_data: List[Dict[str, Any]], include_thematic: bool = False) -> bytes:
        """
        Генерация отчета в формате CSV и возврат в виде байтов.
        
        Args:
            domains_data: Данные о доменах
            include_thematic: Включать ли данные тематического анализа
            
        Returns:
            bytes: Отчет в виде байтов
        """
        try:
            # Создание DataFrame из данных о доменах
            df = pd.DataFrame(domains_data)
            
            # Определение основных колонок для отчета
            columns = [
                "domain", "total_snapshots", "years_covered", 
                "avg_interval_days", "max_gap_days", "is_long_live",
                "first_snapshot_date", "last_snapshot_date"
            ]
            
            # Добавление колонок тематического анализа, если требуется
            if include_thematic:
                thematic_columns = [
                    "main_category", "subcategories", "commercial_value",
                    "target_audience", "use_cases"
                ]
                for col in thematic_columns:
                    if col in df.columns:
                        columns.append(col)
            
            # Фильтрация колонок
            df_filtered = df[columns] if all(col in df.columns for col in columns) else df
            
            # Создание буфера в памяти
            output = io.StringIO()
            
            # Сохранение в CSV
            df_filtered.to_csv(output, index=False)
            
            # Получение строки из буфера и преобразование в байты
            csv_data = output.getvalue().encode('utf-8')
            output.close()
            
            return csv_data
            
        except Exception as e:
            logger.error(f"Error generating CSV bytes: {str(e)}")
            raise
