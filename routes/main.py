from flask import Blueprint, render_template, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from utils.gemini_client import GeminiClient
import structlog

logger = structlog.get_logger()

main = Blueprint('main', __name__)
limiter = Limiter(key_func=get_remote_address)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/sobre')
def sobre():
    return render_template('sobre.html')

@main.route('/golpes-recentes')
def golpes_recentes():
    return render_template('golpes_recentes.html')

@main.route('/dicas-seguranca')
def dicas_seguranca():
    return render_template('dicas_seguranca.html')

@main.route('/denunciar-golpes')
def denunciar_golpes():
    return render_template('denunciar_golpes.html')

@main.route('/verificar', methods=['POST'])
@limiter.limit("10 per minute")
async def verificar_golpe():
    """
    Endpoint to verify potential scams using the Gemini API.
    Rate limited to prevent abuse.
    """
    try:
        if not request.is_json:
            return jsonify({
                'error': 'Content-Type must be application/json',
                'risk_level': 'Indeterminado',
                'summary': 'Erro no formato da requisição.',
                'alerts': ['A requisição deve ser em formato JSON.'],
                'recommendation': 'Tente novamente com o formato correto.'
            }), 400

        data = request.get_json()
        mensagem_usuario = data.get('message', '').strip()
        
        if not mensagem_usuario:
            return jsonify({
                'error': 'Nenhuma mensagem fornecida.',
                'risk_level': 'Indeterminado',
                'summary': 'Mensagem vazia.',
                'alerts': ['Nenhum texto para análise.'],
                'recommendation': 'Por favor, forneça uma mensagem para análise.'
            }), 400

        # Get Gemini client from app context
        gemini_client = GeminiClient(current_app.config['GEMINI_API_KEY'])
        
        prompt = f"""
        Você é um especialista em segurança digital e detecção de fraudes. Analise a seguinte mensagem com extremo cuidado:
        ---
        {mensagem_usuario}
        ---
        [Rest of your existing prompt...]
        """

        response = await gemini_client.generate_content_async(prompt)
        
        return jsonify(response.text), 200

    except Exception as e:
        logger.error("verificar_golpe.failed", error=str(e))
        return jsonify({
            'error': str(e),
            'risk_level': 'Indeterminado',
            'summary': 'Erro interno do servidor.',
            'alerts': ['Ocorreu um erro ao processar sua solicitação.'],
            'recommendation': 'Por favor, tente novamente mais tarde.'
        }), 500 