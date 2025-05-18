from flask import Blueprint, request, jsonify, current_app
from extensions import limiter  # Import the global limiter instance
from utils.analysis_tools import AnalysisTools
from utils.gemini_thread import GeminiThreadManager
import json
import structlog
import asyncio

logger = structlog.get_logger()

analysis_tools_instance = AnalysisTools()
gemini_thread_manager = GeminiThreadManager(max_workers=5)

api = Blueprint('api', __name__)

def create_gemini_model():
    """Create a new Gemini model instance with current app configuration."""
    if not current_app.config.get("GEMINI_API_KEY"):
        logger.error("Gemini API key not configured")
        return None
        
    try:
        return gemini_thread_manager.create_model(
            model_name=current_app.config.get("GEMINI_MODEL", "gemini-1.5-flash"),
            generation_config={"temperature": 0.7, "max_output_tokens": 2048}
            # Safety settings will use defaults from GeminiThreadManager
        )
    except Exception as e:
        logger.error(f"Error creating Gemini model: {str(e)}", exc_info=True)
        return None

@api.route('/verificar', methods=['POST'])
@limiter.limit("10 per minute")  # Rate limit: 10 requests per minute
async def verificar_golpe():
    if not current_app.config.get("GEMINI_API_KEY"):
        logger.error("api.verificar_golpe: Gemini API not configured.")
        return jsonify({'error': 'Serviço de IA não configurado.', 'risk_level': 'Indeterminado'}), 500

    response_data = {
        'risk_level': 'Indeterminado',
        'summary': None,
        'alerts': [],
        'recommendation': None,
        'error': None
    }

    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        data = request.get_json()
        mensagem_usuario = data.get('message', '').strip()
        if not mensagem_usuario:
            return jsonify({'error': 'Nenhuma mensagem fornecida.'}), 400
        
        # Create new model instance for this request
        gemini_model = create_gemini_model()
        if not gemini_model:
            return jsonify({'error': 'Falha ao inicializar modelo Gemini', 'risk_level': 'Indeterminado'}), 500
        
        prompt = f"""
        Você é um especialista em segurança digital e detecção de fraudes. Analise a seguinte mensagem com extremo cuidado:
        ---
        {mensagem_usuario}
        ---
        Retorne uma análise detalhada em formato JSON com as seguintes informações:
        {{
          "risk_level": "string (Valores: Baixo, Médio, Alto, Muito Alto)",
          "summary": "string (Resumo conciso da análise)",
          "alerts": ["string (Pontos suspeitos)"],
          "recommendation": "string (Recomendação principal)"
        }}
        Forneça apenas o objeto JSON como resposta.
        """
        logger.debug(f"api.verificar_golpe: Sending prompt to Gemini: {prompt[:150]}...")
        
        try:
            response = await gemini_thread_manager.generate_content(
                gemini_model,
                prompt,
                generation_config={"temperature": 0.7, "max_output_tokens": 2048}
            )
            logger.debug("api.verificar_golpe: Received response from Gemini.")
            
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                logger.error(f"api.verificar_golpe: Gemini blocked prompt. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                response_data['error'] = f'Bloqueado pela IA: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}'
                return jsonify(response_data), 400

            if not response.text:
                logger.error("api.verificar_golpe: Gemini returned empty text response.")
                response_data['error'] = 'Resposta vazia da IA'
                return jsonify(response_data), 500
                
            cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            try:
                analysis_data = json.loads(cleaned_response)
                return jsonify(analysis_data)
            except json.JSONDecodeError as e:
                logger.error(f"api.verificar_golpe: JSON decode error: {e}. Raw: {cleaned_response[:200]}")
                response_data['error'] = f'Erro ao decodificar JSON da IA: {e}'
                response_data['raw_response'] = cleaned_response
                return jsonify(response_data), 500

        except RuntimeError as e:
            logger.error(f"api.verificar_golpe: Runtime error from Gemini Thread Manager: {str(e)}", exc_info=True)
            response_data['error'] = f'Erro de processamento assíncrono: {str(e)}'
            return jsonify(response_data), 500
        except Exception as e:
            logger.error(f"api.verificar_golpe: Error calling Gemini Thread Manager: {str(e)}", exc_info=True)
            response_data['error'] = f'Falha na comunicação com IA: {str(e)}'
            return jsonify(response_data), 500

    except Exception as e:
        logger.error(f"api.verificar_golpe: Erro inesperado GERAL: {str(e)}", exc_info=True)
        response_data['error'] = f'Erro inesperado no servidor: {str(e)}'
        response_data['summary'] = 'Falha crítica no processamento.'
        response_data['recommendation'] = 'Tente novamente mais tarde.'
        return jsonify(response_data), 500

@api.route('/analyze_image', methods=['POST'])
@limiter.limit("5 per minute")  # Rate limit: 5 requests per minute (more restrictive due to image processing)
async def analyze_image_api():
    final_results = {
        'extracted_text': None,
        'text_analysis': {
            'risk_level': 'Indeterminado',
            'summary': None,
            'alerts': [],
            'recommendation': None,
            'error': None
        }
    }

    try:
        if not current_app.config.get("GEMINI_API_KEY"):
            logger.error("api.analyze_image_api: Gemini API not configured.")
            final_results['text_analysis']['error'] = 'Serviço de IA não configurado.'
            return jsonify(final_results), 500

        if 'image' not in request.files:
            final_results['text_analysis']['error'] = 'Nenhuma imagem fornecida'
            return jsonify(final_results), 400
            
        file = request.files['image']
        if not file or file.filename == '':
            final_results['text_analysis']['error'] = 'Nenhum arquivo selecionado'
            return jsonify(final_results), 400

        image_data = file.read()
        if not image_data:
            final_results['text_analysis']['error'] = 'Arquivo de imagem vazio'
            return jsonify(final_results), 400

        logger.info("api.analyze_image_api: Starting OCR")
        ocr_results = await analysis_tools_instance.analyze_image(image_data)
        
        final_results.update(ocr_results)
        if 'extracted_text' in final_results and final_results['extracted_text']:
            formatted_text = final_results['extracted_text'].replace('\n', '<br>')

        if ocr_results.get('extracted_text') and not ocr_results.get('error'):
            extracted_text = ocr_results['extracted_text'].strip()
            if len(extracted_text) > 5:
                logger.info("api.analyze_image_api: OCRed, analyzing text with Gemini")
                
                # Create new model instance for this request
                gemini_model = create_gemini_model()
                if not gemini_model:
                    final_results['text_analysis']['error'] = 'Falha ao inicializar modelo Gemini'
                    return jsonify(final_results), 500
                
                prompt_for_image_text = f"""
                Analise o seguinte texto extraído de uma imagem para identificar possíveis golpes ou fraudes.
                Texto: --- {extracted_text} ---
                Retorne a análise em formato JSON com: "risk_level", "summary", "alerts", "recommendation".
                Se o texto for lixo de OCR ou muito curto, use "risk_level": "Não Analisável".
                Apenas o JSON como resposta.
                """
                logger.debug(f"api.analyze_image_api: Sending prompt: {prompt_for_image_text[:150]}...")
                
                try:
                    response = await gemini_thread_manager.generate_content(
                        gemini_model,
                        prompt_for_image_text,
                        generation_config={"temperature": 0.7, "max_output_tokens": 1024}
                    )
                    logger.debug("api.analyze_image_api: Received response.")

                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        logger.error(f"api.analyze_image_api: Gemini blocked prompt. Reason: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}")
                        final_results['text_analysis']['error'] = f'Bloqueado pela IA: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}'
                    elif response.text:
                        cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                        try:
                            final_results['text_analysis'] = json.loads(cleaned_response)
                        except json.JSONDecodeError as e:
                            logger.error(f"api.analyze_image_api: JSON decode error: {e}. Raw: {cleaned_response[:200]}")
                            final_results['text_analysis'].update({
                                'error': f'Erro ao decodificar JSON da IA: {e}',
                                'raw_response': cleaned_response
                            })
                    else:
                        logger.error("api.analyze_image_api: Gemini returned empty text response.")
                        final_results['text_analysis']['error'] = 'Resposta vazia da IA'

                except RuntimeError as e:
                    logger.error(f"api.analyze_image_api: Runtime error from Gemini Thread Manager: {str(e)}", exc_info=True)
                    final_results['text_analysis'].update({
                        'error': f'Erro de processamento assíncrono: {str(e)}',
                        'summary': f'Erro no sistema de IA: {str(e)}'
                    })
                except Exception as e:
                    logger.error(f"api.analyze_image_api: Error calling Gemini Thread Manager: {str(e)}", exc_info=True)
                    final_results['text_analysis'].update({
                        'error': f'Falha na comunicação com IA: {str(e)}',
                        'summary': 'Não foi possível obter análise da IA.'
                    })
            else:
                logger.info("api.analyze_image_api: Texto extraído muito curto.")
                final_results['text_analysis'].update({
                    'risk_level': 'Não Analisável',
                    'summary': 'Texto muito curto.'
                })
        else:
            error_msg = ocr_results.get('error', 'Texto não extraído')
            logger.warning(f"api.analyze_image_api: Sem texto do OCR: {error_msg}")
            final_results['text_analysis'].update({
                'risk_level': 'Indeterminado',
                'summary': f'Falha OCR: {error_msg}'
            })
            if 'extracted_text' not in final_results:
                final_results['extracted_text'] = f"[Falha OCR: {error_msg}]"

    except Exception as e:
        logger.error(f"api.analyze_image_api: Erro inesperado GERAL: {str(e)}", exc_info=True)
        if not isinstance(final_results, dict) or not final_results:
            final_results = {'extracted_text': '[Erro antes da extração]', 'error': str(e)}
        
        final_results['text_analysis'] = {
            'error': f'Erro inesperado no servidor: {str(e)}',
            'risk_level': 'Indeterminado',
            'summary': 'Falha crítica no processamento.',
            'alerts': [],
            'recommendation': 'Tente novamente mais tarde.'
        }
        return jsonify(final_results), 500

    return jsonify(final_results) 