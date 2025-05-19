import os
import json
import uuid
import logging
import io
from typing import Dict, List, Any, Optional
from flask import Flask, request, jsonify, send_file, Blueprint
from flask_cors import CORS
from datetime import datetime

# Импорт сервисов (обновлены для новой структуры)
from services.wayback_service import WaybackService
from services.openrouter_service import OpenRouterService
from services.report_service import ReportService

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание Blueprint для API
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Инициализация сервисов
wayback_service = WaybackService(
    user_agent=os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
)
openrouter_service = OpenRouterService(
    api_key=os.getenv("OPENROUTER_API_KEY")
)
report_service = ReportService(
    output_dir=os.getenv("REPORTS_DIR", os.path.join(os.getcwd(), "reports"))
)

# Хранилище задач (в реальном приложении лучше использовать базу данных)
tasks = {}

@api_bp.route('/analysis/tasks', methods=['POST'])
async def create_analysis_task():
    """
    Создание задачи анализа доменов.
    """
    try:
        data = request.json
        domains = data.get('domains', [])
        match_type = data.get('match_type', 'domain')
        collapse = data.get('collapse', 'timestamp')
        limit = data.get('limit', 1000)
        
        if not domains:
            return jsonify({"error": "No domains provided"}), 400
        
        # Создание уникального ID задачи
        task_id = str(uuid.uuid4())
        
        # Запуск анализа доменов
        results = await wayback_service.analyze_domains(domains, match_type, collapse, limit)
        
        # Сохранение результатов
        tasks[task_id] = {
            "id": task_id,
            "status": "completed",
            "created_at": datetime.now().isoformat(),
            "domains": domains,
            "results": results
        }
        
        return jsonify({
            "task_id": task_id,
            "status": "completed",
            "message": f"Analysis completed for {len(domains)} domains"
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating analysis task: {str(e)}", exc_info=True)
        return jsonify({"error": str(e), "type": type(e).__name__}), 500

@api_bp.route('/analysis/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """
    Получение статуса задачи.
    """
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = tasks[task_id]
    return jsonify({
        "task_id": task_id,
        "status": task["status"],
        "created_at": task["created_at"],
        "domains_count": len(task["domains"])
    })

@api_bp.route('/analysis/tasks/<task_id>/results', methods=['GET'])
def get_task_results(task_id):
    """
    Получение результатов задачи.
    """
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = tasks[task_id]
    if task["status"] != "completed":
        return jsonify({"error": "Task not completed yet"}), 400
    
    return jsonify({
        "task_id": task_id,
        "results": task["results"]
    })

@api_bp.route('/reports/<task_id>/<format>', methods=['GET'])
def get_report(task_id, format):
    """
    Получение отчета в указанном формате.
    """
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = tasks[task_id]
    if task["status"] != "completed":
        return jsonify({"error": "Task not completed yet"}), 400
    
    include_thematic = request.args.get('include_thematic', 'false').lower() == 'true'
    
    try:
        if format == 'excel':
            excel_data = report_service.generate_excel_bytes(task["results"], include_thematic)
            return send_file(
                io.BytesIO(excel_data),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f"drop_report_{task_id}.xlsx"
            )
        elif format == 'csv':
            csv_data = report_service.generate_csv_bytes(task["results"], include_thematic)
            return send_file(
                io.BytesIO(csv_data),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f"drop_report_{task_id}.csv"
            )
        elif format == 'json':
            return jsonify(task["results"])
        else:
            return jsonify({"error": "Unsupported format"}), 400
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route('/thematic-analysis/<task_id>', methods=['POST'])
async def start_thematic_analysis(task_id):
    """
    Запуск тематического анализа для задачи.
    """
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = tasks[task_id]
    if task["status"] != "completed":
        return jsonify({"error": "Task not completed yet"}), 400
    
    try:
        # Получение результатов анализа доменов
        results = task["results"]
        
        # Запуск тематического анализа для каждого домена
        for i, result in enumerate(results):
            domain = result.get("domain")
            if domain and "error" not in result:
                # Получение содержимого домена (в реальном приложении нужно реализовать парсинг)
                content = f"Domain: {domain}, Snapshots: {result.get('total_snapshots', 0)}"
                
                # Запуск тематического анализа
                thematic_result = openrouter_service.analyze_domain_theme(domain, content)
                
                # Обновление результатов
                results[i].update(thematic_result)
        
        # Обновление задачи
        task["results"] = results
        task["thematic_analysis_completed"] = True
        
        return jsonify({
            "task_id": task_id,
            "status": "completed",
            "message": "Thematic analysis completed"
        })
        
    except Exception as e:
        logger.error(f"Error starting thematic analysis: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route('/thematic-analysis/<task_id>/results', methods=['GET'])
def get_thematic_analysis_results(task_id):
    """
    Получение результатов тематического анализа.
    """
    if task_id not in tasks:
        return jsonify({"error": "Task not found"}), 404
    
    task = tasks[task_id]
    if not task.get("thematic_analysis_completed", False):
        return jsonify({"error": "Thematic analysis not completed yet"}), 400
    
    return jsonify({
        "task_id": task_id,
        "results": task["results"]
    })

@api_bp.route('/ai-agents', methods=['POST'])
def create_ai_agent():
    """
    Создание ИИ агента с произвольным промптом и задачей.
    """
    try:
        data = request.json
        name = data.get('name')
        description = data.get('description')
        prompt_template = data.get('prompt_template')
        model = data.get('model', 'openai/gpt-4-turbo')
        
        if not all([name, description, prompt_template]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Создание ИИ агента
        result = openrouter_service.create_ai_agent(name, description, prompt_template, model)
        
        if result.get("success", False):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error creating AI agent: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route('/ai-agents', methods=['GET'])
def list_ai_agents():
    """
    Получение списка ИИ агентов.
    """
    try:
        # Получение списка агентов
        result = openrouter_service.list_saved_models()
        
        if result.get("success", False):
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error listing AI agents: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route('/trained-models', methods=['POST'])
def save_trained_model():
    """
    Сохранение обученной модели.
    """
    try:
        data = request.json
        model_name = data.get('model_name')
        training_data = data.get('training_data')
        base_model = data.get('base_model', 'openai/gpt-3.5-turbo')
        
        if not all([model_name, training_data]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Сохранение обученной модели
        result = openrouter_service.save_trained_model(model_name, training_data, base_model)
        
        if result.get("success", False):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error saving trained model: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@api_bp.route('/trained-models', methods=['GET'])
def list_trained_models():
    """
    Получение списка обученных моделей.
    """
    try:
        # Получение списка моделей
        result = openrouter_service.list_saved_models()
        
        if result.get("success", False):
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Error listing trained models: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# Добавление обработчика для корневого URL
def create_app():
    """
    Создание и настройка приложения Flask.
    """
    app = Flask(__name__)
    
    # Настройка CORS с улучшенной безопасностью
    CORS(app, resources={
        r"/api/*": {
            "origins": os.getenv("ALLOWED_ORIGINS", "*").split(","),
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # Регистрация Blueprint
    app.register_blueprint(api_bp)
    
    # Добавление обработчика для корневого URL
    @app.route('/', methods=['GET'])
    def index():
        return jsonify({
            "status": "ok",
            "message": "API is running",
            "version": "1.0",
            "endpoints": {
                "POST /api/v1/analysis/tasks": "Create analysis task",
                "GET /api/v1/analysis/tasks/<task_id>": "Get task status",
                "GET /api/v1/analysis/tasks/<task_id>/results": "Get task results",
                "GET /api/v1/reports/<task_id>/<format>": "Get report",
                "POST /api/v1/thematic-analysis/<task_id>": "Start thematic analysis",
                "GET /api/v1/thematic-analysis/<task_id>/results": "Get thematic analysis results",
                "POST /api/v1/ai-agents": "Create AI agent",
                "GET /api/v1/ai-agents": "List AI agents",
                "POST /api/v1/trained-models": "Save trained model",
                "GET /api/v1/trained-models": "List trained models"
            }
        })
    
    # Добавление проверки работоспособности (health check)
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0"
        })
    
    # Добавление глобальных обработчиков ошибок
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Resource not found", "details": str(error)}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({
            "error": "Method not allowed", 
            "details": str(error),
            "allowed_methods": error.valid_methods if hasattr(error, 'valid_methods') else []
        }), 405

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "Internal server error", "details": str(error)}), 500
    
    # Добавление логирования запросов
    @app.before_request
    def log_request_info():
        app.logger.info('Request: %s %s', request.method, request.path)
        app.logger.debug('Headers: %s', request.headers)
        app.logger.debug('Body: %s', request.get_data())

    @app.after_request
    def log_response_info(response):
        app.logger.info('Response: %s %s %s', request.method, request.path, response.status)
        return response
    
    return app

# Создание приложения
app = create_app()

if __name__ == "__main__":
    # Запуск приложения
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("DEBUG", "False").lower() == "true")
