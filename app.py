import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import json # Para tentar analisar a resposta do Gemini se não for JSON válido
import datetime
import uuid
from utils.analysis_tools import AnalysisTools
import asyncio
import logging
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import platform
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from flask_caching import Cache
import structlog
from config import config

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Load environment variables
load_dotenv()
logger.info("Environment variables loaded")

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'temp_uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize analysis tools
analysis_tools = AnalysisTools()

# Configuração da API do Google Gemini
try:
    gemini_api_key = os.getenv("GOOGLE_API_KEY")
    logger.info("Attempting to configure Gemini API...")
    
    if not gemini_api_key:
        raise ValueError("API Key do Google Gemini não encontrada. Verifique o arquivo .env ou as variáveis de ambiente.")
    
    genai.configure(api_key=gemini_api_key)
    logger.info("Basic API configuration completed")
    
    # Initialize the model with more detailed error handling
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Model initialized, testing connection...")
        
        # Test the model with a simple prompt
        # Note: This test call does not use the custom safety_settings, so it might pass even if they are malformed for other calls.
        test_response = model.generate_content("Test connection. Respond with 'OK'.")
        if test_response and test_response.text:
            logger.info(f"Test response received: {test_response.text}")
            print("✅ Modelo Gemini configurado e testado com sucesso.")
        else:
            raise Exception("Received empty response from model during test")
            
    except Exception as model_error:
        logger.error(f"Error initializing or testing model: {str(model_error)}")
        print(f"❌ Erro ao inicializar ou testar modelo: {str(model_error)}")
        model = None
        raise

except Exception as e:
    logger.error(f"Failed to configure Gemini API: {str(e)}")
    print(f"❌ Erro na configuração do Gemini: {str(e)}")
    model = None

# Initialize extensions
csrf = CSRFProtect()
cache = Cache()
limiter = Limiter(key_func=get_remote_address)
talisman = Talisman()

def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Initialize extensions
    csrf.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    talisman.init_app(app,
                     content_security_policy={
                         'default-src': "'self'",
                         'img-src': "'self' data: https:",
                         'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
                         'style-src': "'self' 'unsafe-inline'",
                         'font-src': "'self' https://fonts.gstatic.com",
                     },
                     force_https=False)  # Set to True in production
    
    # Register blueprints
    from routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    
    return app

# Create the application instance
app = create_app()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sobre')
def sobre():
    return render_template('sobre.html')

@app.route('/golpes-recentes')
def golpes_recentes():
    return render_template('golpes_recentes.html')

@app.route('/dicas-seguranca')
def dicas_seguranca():
    return render_template('dicas_seguranca.html')

@app.route('/denunciar-golpes')
def denunciar_golpes():
    return render_template('denunciar_golpes.html')

@app.route('/verificar', methods=['POST'])
async def verificar_golpe():
    if not model:
        logger.error("Attempted to use unconfigured model")
        return jsonify({
            'error': 'Modelo Gemini não está configurado. Verifique o console do servidor para mais detalhes.',
            'risk_level': 'Indeterminado',
            'summary': 'Serviço temporariamente indisponível.',
            'alerts': ['Sistema de análise não está disponível no momento.'],
            'recommendation': 'Por favor, tente novamente mais tarde.'
        }), 500

    data = request.get_json()
    mensagem_usuario = data.get('message', '')
    
    logger.info(f"Received message for analysis: {mensagem_usuario[:50]}...")

    if not mensagem_usuario:
        return jsonify({
            'error': 'Nenhuma mensagem fornecida.',
            'risk_level': 'Indeterminado',
            'summary': 'Mensagem vazia.',
            'alerts': ['Nenhum texto para análise.'],
            'recommendation': 'Por favor, forneça uma mensagem para análise.'
        }), 400

    prompt = f"""
    Você é um especialista em segurança digital e detecção de fraudes. Analise a seguinte mensagem com extremo cuidado:
    ---
    {mensagem_usuario}
    ---
    Retorne uma análise detalhada em formato JSON com as seguintes informações:

    {{
      "risk_level": string (Valores: "Baixo", "Médio", "Alto", "Muito Alto"),
      "summary": string (Resumo conciso da análise),
      "alerts": array de strings (Pontos suspeitos),
      "recommendation": string (Recomendação principal),
      "analysis_details": {{
        "fraud_patterns": array (Padrões de fraude identificados),
        "urgency_indicators": array (Indicadores de urgência/pressão),
        "financial_risk": {{
          "present": boolean,
          "type": string,
          "severity": string
        }},
        "data_collection": {{
          "personal_info_requested": array,
          "financial_info_requested": array
        }},
        "technical_indicators": {{
          "has_links": boolean,
          "has_phone_numbers": boolean,
          "has_suspicious_contacts": boolean
        }},
        "identified_urls": array (Lista de URLs encontradas na mensagem, cada uma com formato: {{"url": string, "status": "Pending Check"}}),
        "url_safety_summary": string (Resumo da análise de segurança das URLs, será atualizado após verificação),
        "social_engineering": {{
          "manipulation_tactics": array,
          "pressure_points": array
        }}
      }},
      "safety_tips": array (Dicas específicas de segurança),
      "confidence_score": number (0.0 a 1.0)
    }}

    Analise especialmente:
    1. Padrões comuns de golpes conhecidos
    2. Táticas de engenharia social
    3. Indicadores de urgência ou pressão
    4. Solicitações de informações sensíveis
    5. Elementos técnicos suspeitos (links, números, etc.)
    6. Riscos financeiros potenciais
    7. Manipulação psicológica
    8. URLs presentes na mensagem (extraia e liste todas as URLs encontradas)

    Forneça apenas o objeto JSON como resposta, sem texto adicional.
    """

    try:
        logger.info("Generating content with Gemini...")
        
        # MODIFIED: Corrected safety_settings to use enums
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 2048,
        }
        
        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        logger.info(f"Raw Gemini response object: {response}")
        
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason_name = getattr(response.prompt_feedback.block_reason, 'name', str(response.prompt_feedback.block_reason))
            logger.error(f"Prompt blocked by Gemini. Reason: {block_reason_name}")
            logger.error(f"Safety ratings for blocked prompt: {response.prompt_feedback.safety_ratings}")
            return jsonify({
                'risk_level': 'Indeterminado',
                'summary': f'A análise foi bloqueada pela política de segurança da IA (Motivo: {block_reason_name}).',
                'alerts': ['O conteúdo fornecido ou a análise solicitada podem ter violado as diretrizes de uso.'],
                'recommendation': 'Tente reformular sua mensagem ou verifique se ela não contém conteúdo explicitamente proibido.',
                'error_details': f'Prompt blocked due to {block_reason_name}'
            }), 400

        if not response.candidates:
            logger.error("No candidates found in Gemini response.")
            raise Exception("Nenhum candidato encontrado na resposta do Gemini.")

        candidate = response.candidates[0]
        
        # Get the FinishReason enum type from the instance
        FinishReasonEnumType = type(candidate.finish_reason)

        # Compare using the dynamically obtained enum type
        if candidate.finish_reason != FinishReasonEnumType.STOP and \
           candidate.finish_reason != FinishReasonEnumType.MAX_TOKENS:
            
            finish_reason_name = getattr(candidate.finish_reason, 'name', str(candidate.finish_reason))
            safety_ratings_detail = candidate.safety_ratings if candidate.safety_ratings else "N/A"
            logger.error(f"Gemini response generation stopped abnormally. Finish reason: {finish_reason_name}. Safety Ratings: {safety_ratings_detail}")

            error_summary = f"A geração da resposta foi interrompida. Motivo: {finish_reason_name}."
            error_alerts = [f"Detalhes: {safety_ratings_detail}"]
            
            if candidate.finish_reason == FinishReasonEnumType.SAFETY:
                 error_summary = "A resposta da IA foi interrompida devido a filtros de segurança."
                 error_alerts = [f"Detalhes do filtro de segurança: {safety_ratings_detail}"]
            elif candidate.finish_reason == FinishReasonEnumType.RECITATION:
                 error_summary = "A resposta da IA foi interrompida devido a problemas de recitação."
                 error_alerts = ["A IA evitou citar material protegido excessivamente."]
            
            return jsonify({
                'risk_level': 'Indeterminado',
                'summary': error_summary,
                'alerts': error_alerts,
                'recommendation': 'Tente novamente ou reformule a mensagem. Se o problema persistir, o conteúdo pode estar sendo bloqueado.',
                'error_details': f'Generation stopped: {finish_reason_name}, Safety: {safety_ratings_detail}'
            }), 500

        if not candidate.content or not candidate.content.parts or not candidate.content.parts[0].text:
            logger.error(f"Received empty or incomplete content part from Gemini. Finish reason: {getattr(candidate.finish_reason, 'name', str(candidate.finish_reason))}")
            raise Exception("Resposta com conteúdo vazio ou incompleto do modelo Gemini.")

        generated_text = candidate.content.parts[0].text
        logger.info("Response text received, processing...")
        
        cleaned_response_text = generated_text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
        if cleaned_response_text.endswith("```"):
            cleaned_response_text = cleaned_response_text[:-3]
        
        try:
            analysis_data = json.loads(cleaned_response_text)
            logger.info("Successfully parsed JSON response")
            
            # Process URLs if present in the analysis
            if 'analysis_details' in analysis_data and 'identified_urls' in analysis_data['analysis_details']:
                urls_to_check = analysis_data['analysis_details']['identified_urls']
                processed_urls_info = []
                any_suspicious_url_found = False

                if urls_to_check:  # Check if the list is not empty
                    # Create a list of just the URL strings for batch checking
                    url_strings = [item.get('url') for item in urls_to_check if item.get('url')]
                    
                    if url_strings:
                        logger.info(f"Found URLs for Safe Browsing check: {url_strings}")
                        # analyze_urls expects a list of URL strings and returns a dict with 'url_analysis'
                        safe_browsing_results_wrapper = await analysis_tools.analyze_urls(url_strings)
                        
                        # Create a mapping from URL string to its Safe Browsing analysis
                        sb_analysis_map = {
                            entry['url']: entry 
                            for entry in safe_browsing_results_wrapper.get('url_analysis', [])
                        }

                        for url_item_dict in urls_to_check:  # Iterate through original list from Gemini
                            url_str = url_item_dict.get('url')
                            if url_str and url_str in sb_analysis_map:
                                sb_result = sb_analysis_map[url_str]
                                url_item_dict['status'] = sb_result.get('status_message', 'Check Error')
                                url_item_dict['is_safe'] = sb_result.get('is_safe')
                                url_item_dict['threat_types'] = sb_result.get('threat_types', [])
                                if sb_result.get('is_safe') is False:
                                    any_suspicious_url_found = True
                            else:
                                url_item_dict['status'] = 'Not checked or URL missing'
                            processed_urls_info.append(url_item_dict)
                        
                        analysis_data['analysis_details']['identified_urls'] = processed_urls_info  # Update with results

                        # Update the URL safety summary
                        if any_suspicious_url_found:
                            analysis_data['analysis_details']['url_safety_summary'] = "Alerta: Uma ou mais URLs foram marcadas como potencialmente perigosas pelo Google Safe Browsing."
                            # If we found dangerous URLs, make sure the risk level reflects this
                            if analysis_data.get('risk_level') in ['Baixo', 'Médio']:
                                analysis_data['risk_level'] = 'Alto'
                                analysis_data['alerts'].append('URLs potencialmente perigosas detectadas pelo Google Safe Browsing.')
                        elif urls_to_check and url_strings:  # if there were URLs and none were suspicious
                            analysis_data['analysis_details']['url_safety_summary'] = "URLs verificadas pelo Google Safe Browsing e nenhuma ameaça imediata foi encontrada."
            
            analysis_data['timestamp'] = datetime.datetime.now().isoformat()
            analysis_data['analysis_id'] = str(uuid.uuid4())
            
            return jsonify(analysis_data)

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in /verificar: {str(e)}")
            return jsonify({
                'risk_level': 'Indeterminado',
                'summary': 'Erro ao processar a análise detalhada (formato JSON inválido).',
                'alerts': ['Não foi possível completar a análise detalhada devido a um problema de formato.'],
                'recommendation': 'Por favor, tente novamente. Se o problema persistir, o modelo pode estar retornando dados inesperados.',
                'error_details': str(e)
            }), 500
        except Exception as e:
            logger.error(f"General error in analysis for /verificar. Type: {type(e)}, Args: {e.args}, Message: {str(e)}", exc_info=True)
            if hasattr(e, 'response') and e.response:
                logger.error(f"Underlying API Response (if available from exception): {e.response}")

            error_message_str = str(e)
            user_summary = 'Erro ao processar a mensagem.'
            user_alerts = ['Ocorreu um erro durante a análise.']
            
            if any(keyword in error_message_str.lower() for keyword in ["blocked", "safety", "filtros de segurança", "dangerous_content", "policy"]):
                user_summary = 'Análise bloqueada ou interrompida por política de segurança.'
                user_alerts = ['O conteúdo enviado ou a análise solicitada podem ter acionado filtros de segurança da IA.']
            elif "vazia" in error_message_str or "incomplete" in error_message_str:
                user_summary = 'A IA não forneceu uma resposta completa.'
                user_alerts = ['A análise não pôde ser concluída pela IA.']

            return jsonify({
                'risk_level': 'Indeterminado',
                'summary': user_summary,
                'alerts': user_alerts,
                'recommendation': 'Por favor, tente novamente mais tarde ou reformule sua mensagem.',
                'error_details': error_message_str
            }), 500

    except Exception as e:
        logger.error(f"General error in /verificar: {str(e)}", exc_info=True)
        return jsonify({
            'risk_level': 'Indeterminado',
            'summary': 'Erro ao processar a análise detalhada.',
            'alerts': ['Ocorreu um erro ao processar a análise detalhada.'],
            'recommendation': 'Por favor, tente novamente mais tarde ou reformule sua mensagem.',
            'error_details': str(e)
        }), 500

@app.route('/analyze_image', methods=['POST'])
async def analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'Nenhuma imagem fornecida'}), 400
    
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    try:
        image_data = file.read()
        # AnalysisTools.analyze_image now only does OCR and returns base results
        ocr_results = await analysis_tools.analyze_image(image_data) 
        
        final_results = ocr_results.copy() # Start with OCR results
        final_results['text_analysis'] = None # Initialize text_analysis field

        # If text was extracted by OCR, analyze it using app.py's helper
        if ocr_results.get('extracted_text') and not ocr_results.get('error'):
            # Avoid analyzing placeholders or very short OCR garbage
            if len(ocr_results['extracted_text'].strip()) > 5: # Arbitrary short length check
                logger.info("Image OCRed, now analyzing extracted text with app's Gemini model...")
                # Use the app's own async helper for Gemini analysis
                text_analysis_from_gemini = await analyze_text_content(ocr_results['extracted_text'])
                final_results['text_analysis'] = text_analysis_from_gemini

                # If URLs were found in the OCRed text, analyze them
                if ocr_results.get('urls_found'):
                    logger.info(f"Analyzing {len(ocr_results['urls_found'])} URLs found in OCRed text...")
                    url_analysis_results = await analysis_tools.analyze_urls(ocr_results['urls_found'])
                    final_results['url_analysis'] = url_analysis_results.get('url_analysis', [])
                    
                    # If any URLs are suspicious, add this information to the text analysis
                    suspicious_urls = url_analysis_results.get('suspicious_urls_detected', [])
                    if suspicious_urls and isinstance(final_results['text_analysis'], dict):
                        if final_results['text_analysis'].get('risk_level') in ['Baixo', 'Médio']:
                            final_results['text_analysis']['risk_level'] = 'Alto'
                        if 'alerts' in final_results['text_analysis']:
                            final_results['text_analysis']['alerts'].append(
                                'URLs potencialmente perigosas detectadas no texto da imagem.'
                            )
            else:
                logger.info("Extracted OCR text too short or empty, skipping Gemini analysis.")
                final_results['text_analysis'] = {
                    'risk_level': 'Não Analisável',
                    'summary': 'Texto extraído da imagem muito curto ou ilegível para análise pela IA.',
                    'alerts': [],
                    'recommendation': 'Verifique a imagem manualmente.'
                }
        elif ocr_results.get('error'):
            logger.info(f"OCR error, skipping Gemini analysis: {ocr_results.get('error')}")
            final_results['text_analysis'] = {
                'risk_level': 'Indeterminado',
                'summary': f"Erro na extração de texto da imagem: {ocr_results.get('error')}",
                'alerts': ['Não foi possível analisar o texto da imagem.'],
                'recommendation': 'Tente uma imagem mais nítida ou verifique a configuração do OCR.'
            }

        return jsonify(final_results)
    
    except Exception as e:
        logger.error(f"Error in /analyze_image route: {str(e)}", exc_info=True)
        return jsonify({
            'error': str(e),
            'text_analysis': {
                'risk_level': 'Indeterminado',
                'summary': 'Erro ao processar a imagem.',
                'alerts': ['Ocorreu um erro durante o processamento da imagem.'],
                'recommendation': 'Por favor, tente novamente com outra imagem.'
            }
        }), 500

@app.route('/verify_document', methods=['POST'])
async def verify_document():
    if 'document' not in request.files:
        return jsonify({'error': 'Nenhum documento fornecido'}), 400
    
    file = request.files['document']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    
    try:
        document_data = file.read()
        results = await analysis_tools.verify_document(document_data) # This now uses corrected AnalysisTools
        
        # If text was extracted, analyze it using our app.py's helper
        if results.get('text_content') and not results.get('gemini_analysis'): # Check if analysis_tools already did it
            # Assuming 'text_content' from verify_document is what needs to be analyzed
            # Avoid analyzing placeholders like "[Conteúdo PDF não extraído]"
            if results['text_content'] and not results['text_content'].startswith("["): 
                logger.info("Document text extracted, now analyzing with app's Gemini model...")
                text_analysis_result = await analyze_text_content(results['text_content'])
                results['text_analysis'] = text_analysis_result
        elif results.get('gemini_analysis'): # if analysis_tools did it
             results['text_analysis'] = results.pop('gemini_analysis')
        
        return jsonify(results)
    
    except Exception as e:
        logger.error(f"Error in /verify_document: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/check_url', methods=['POST'])
async def check_url():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'Nenhuma URL fornecida'}), 400
    
    try:
        results = await analysis_tools.analyze_urls([url])
        return jsonify(results)
    
    except Exception as e:
        logger.error(f"Error in /check_url: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

async def analyze_text_content(text: str):
    """Helper function to analyze text content using Gemini (used by image/doc analysis)"""
    if not model:
        logger.error("Attempted to use unconfigured model in analyze_text_content")
        return {'error': 'Modelo Gemini não está configurado', 'risk_level': 'Indeterminado'}

    # Simplified prompt for extracted text, expecting a similar JSON structure
    # as the main /verificar endpoint for consistency in the frontend.
    prompt = f"""
    Analise o seguinte texto, que foi extraído de uma imagem ou documento, para identificar possíveis golpes ou fraudes.
    Se o texto for muito curto, genérico, ou claramente um erro de OCR (ex: ""), indique baixo risco ou incapacidade de análise.
    Texto:
    ---
    {text}
    ---
    Retorne a análise em formato JSON com os campos: "risk_level", "summary", "alerts", "recommendation".
    Exemplo de campos:
    "risk_level": string (Valores: "Baixo", "Médio", "Alto", "Muito Alto", "Não Analisável"),
    "summary": string (Resumo conciso da análise do texto extraído),
    "alerts": array de strings (Pontos suspeitos no texto extraído),
    "recommendation": string (Recomendação baseada no texto extraído)
    
    Se o texto for claramente um lixo de OCR ou muito curto para análise significativa, use "risk_level": "Não Analisável".
    Forneça apenas o objeto JSON como resposta.
    """
    
    try:
        # MODIFIED: Corrected safety_settings to use enums
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        }
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 1024, # Potentially smaller for extracted text
        }

        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        # Proper handling of response, similar to /verificar
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            reason = getattr(response.prompt_feedback.block_reason, 'name', str(response.prompt_feedback.block_reason))
            logger.error(f"Prompt blocked in analyze_text_content. Reason: {reason}")
            return {'error': f'Análise de texto bloqueada ({reason})', 'risk_level': 'Indeterminado'}

        if not response.candidates:
            logger.error("No candidates in analyze_text_content response.")
            return {'error': 'Sem candidatos na resposta da IA para texto extraído', 'risk_level': 'Indeterminado'}

        candidate = response.candidates[0]
        
        # Get the FinishReason enum type from the instance
        FinishReasonEnumType = type(candidate.finish_reason)
        
        # Compare using the dynamically obtained enum type
        if candidate.finish_reason != FinishReasonEnumType.STOP and \
           candidate.finish_reason != FinishReasonEnumType.MAX_TOKENS:
            reason = getattr(candidate.finish_reason, 'name', str(candidate.finish_reason))
            logger.error(f"Abnormal finish reason in analyze_text_content: {reason}. Ratings: {candidate.safety_ratings}")
            return {'error': f'Análise de texto interrompida ({reason})', 'risk_level': 'Indeterminado', 'summary': f'Interrupção: {reason}'}

        if not candidate.content or not candidate.content.parts or not candidate.content.parts[0].text:
            logger.error("Empty content part in analyze_text_content response.")
            return {'error': 'Resposta vazia da IA para texto extraído', 'risk_level': 'Indeterminado'}

        generated_text = candidate.content.parts[0].text
        cleaned_response_text = generated_text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
        if cleaned_response_text.endswith("```"):
            cleaned_response_text = cleaned_response_text[:-3]
        
        return json.loads(cleaned_response_text)
    
    except json.JSONDecodeError as e:
        raw_resp_text = generated_text if 'generated_text' in locals() else "N/A"
        logger.error(f"JSON decode error in analyze_text_content. Raw: {raw_resp_text}. Error: {str(e)}")
        return {'error': f'Erro ao decodificar JSON da análise de texto: {str(e)}', 'raw_response': raw_resp_text, 'risk_level': 'Indeterminado'}
    except Exception as e:
        logger.error(f"Error analyzing extracted text with Gemini: Type: {type(e)}, Args: {e.args}, Message: {str(e)}")
        return {'error': f'Erro ao analisar texto extraído: {str(e)}', 'risk_level': 'Indeterminado'}

if __name__ == '__main__':
    # Ensure TESSERACT_PATH is set if on Windows and Tesseract is not in default Program Files
    if platform.system() == "Windows" and not os.getenv('TESSERACT_PATH'):
        # Example path, user might need to change this or set it in .env
        default_tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if not os.path.exists(default_tesseract_path):
            logger.warning("Tesseract default path not found. Consider setting TESSERACT_PATH in your .env file if OCR fails.")
        # pytesseract.pytesseract.tesseract_cmd is typically set in AnalysisTools __init__

    app.run(debug=True)