"""Main routes for the application."""
from flask import Blueprint, render_template, request, current_app, redirect, url_for, flash
import structlog
import json
import asyncio
from utils.analysis_tools import AnalysisTools
from routes.api import gemini_thread_manager, create_gemini_model
from flask_wtf.csrf import validate_csrf, ValidationError as CSRFValidationError
from werkzeug.exceptions import Forbidden

logger = structlog.get_logger()
main = Blueprint('main', __name__)
analysis_tools = AnalysisTools()

@main.route('/')
def index():
    """Render the main landing page."""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error("index.failed", error=str(e))
        return render_template('errors/500.html'), 500

@main.route('/process_analysis', methods=['POST'])
def process_analysis():
    """Process text or image analysis request synchronously."""
    try:
        # Validate CSRF token
        try:
            validate_csrf(request.form.get('csrf_token'))
        except CSRFValidationError as e:
            logger.error(f"CSRF validation failed: {e.args[0] if e.args else str(e)}")
            flash('Erro de segurança (CSRF). Por favor, tente novamente.', 'error')
            return redirect(url_for('main.index'))

        submission = {
            'input_type': None,
            'original_input': None,
            'extracted_text': None
        }
        
        analysis = {
            'text_analysis': {
                'risk_level': 'Indeterminado',
                'summary': None,
                'alerts': [],
                'recommendation': None,
                'error': None
            }
        }
        
        try:
            # Check if Gemini is configured
            if not current_app.config.get("GEMINI_API_KEY"):
                flash('Serviço de IA não configurado.', 'error')
                return redirect(url_for('main.index'))

            # Create Gemini model
            gemini_model = create_gemini_model()
            if not gemini_model:
                flash('Falha ao inicializar modelo de IA.', 'error')
                return redirect(url_for('main.index'))

            # Handle text analysis
            if 'message' in request.form:
                message = request.form['message'].strip()
                if not message:
                    flash('Por favor, forneça uma mensagem para análise.', 'warning')
                    return redirect(url_for('main.index'))

                submission['input_type'] = 'Texto'
                submission['original_input'] = message

                # Prepare prompt for text analysis
                prompt = f"""
                Você é um especialista em segurança digital e detecção de fraudes. Analise a seguinte mensagem com extremo cuidado:
                ---
                {message}
                ---
                Retorne uma análise detalhada em formato JSON com as seguintes informações:
                {{
                  "risk_level": "string (Valores: Baixo, Médio, Alto, Muito Alto)",
                  "summary": "string (Resumo conciso da análise)",
                  "alerts": ["string (Pontos suspeitos)"],
                  "recommendation": "string (Recomendação principal)",
                  "analysis_details": {{
                    "suspicious_patterns": ["string (Padrões suspeitos identificados)"],
                    "language_analysis": "string (Análise do tom e linguagem)",
                    "common_scam_indicators": ["string (Indicadores comuns de golpe)"],
                    "urgency_level": "string (Nível de urgência usado na mensagem)",
                    "credibility_factors": ["string (Fatores que afetam a credibilidade)"]
                  }}
                }}
                Forneça apenas o objeto JSON como resposta.
                """

                # Run Gemini analysis synchronously
                try:
                    response = asyncio.run(gemini_thread_manager.generate_content(
                        gemini_model,
                        prompt,
                        generation_config={"temperature": 0.7, "max_output_tokens": 2048}
                    ))
                    
                    if response.prompt_feedback and response.prompt_feedback.block_reason:
                        analysis['text_analysis']['error'] = f'Conteúdo bloqueado: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}'
                    elif response.text:
                        cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                        analysis['text_analysis'] = json.loads(cleaned_response)
                    else:
                        analysis['text_analysis']['error'] = 'Resposta vazia da IA'
                    
                except json.JSONDecodeError as e:
                    logger.error(f"process_analysis: JSON decode error: {e}")
                    analysis['text_analysis']['error'] = 'Erro ao processar resposta da IA'
                except Exception as e:
                    logger.error(f"process_analysis: Gemini error: {e}", exc_info=True)
                    analysis['text_analysis']['error'] = f'Erro na análise: {str(e)}'

            # Handle image analysis
            elif 'image' in request.files:
                file = request.files['image']
                if not file or file.filename == '':
                    flash('Por favor, selecione uma imagem para análise.', 'warning')
                    return redirect(url_for('main.index'))

                submission['input_type'] = 'Imagem'

                # Validate file type
                if not file.content_type in ['image/jpeg', 'image/png', 'image/webp']:
                    flash('Formato de arquivo não suportado. Use PNG, JPEG ou WebP.', 'error')
                    return redirect(url_for('main.index'))

                image_data = file.read()
                if not image_data:
                    flash('Arquivo de imagem vazio.', 'error')
                    return redirect(url_for('main.index'))

                # Check file size (5MB limit)
                if len(image_data) > 5 * 1024 * 1024:
                    flash('Arquivo muito grande. Limite máximo é 5MB.', 'error')
                    return redirect(url_for('main.index'))

                # Run OCR analysis synchronously
                try:
                    ocr_results = asyncio.run(analysis_tools.analyze_image(image_data))
                    submission['extracted_text'] = ocr_results.get('extracted_text', '')

                    if ocr_results.get('extracted_text') and not ocr_results.get('error'):
                        extracted_text = ocr_results['extracted_text'].strip()
                        if len(extracted_text) > 5:
                            # Prepare prompt for image text analysis
                            prompt = f"""
                            Analise o seguinte texto extraído de uma imagem para identificar possíveis golpes ou fraudes.
                            Texto: --- {extracted_text} ---
                            Retorne a análise em formato JSON com:
                            {{
                              "risk_level": "string (Valores: Baixo, Médio, Alto, Muito Alto, Não Analisável)",
                              "summary": "string (Resumo conciso da análise)",
                              "alerts": ["string (Pontos suspeitos)"],
                              "recommendation": "string (Recomendação principal)",
                              "analysis_details": {{
                                "suspicious_patterns": ["string"],
                                "credibility_factors": ["string"],
                                "context_analysis": "string"
                              }}
                            }}
                            Se o texto for lixo de OCR ou muito curto, use "risk_level": "Não Analisável".
                            Apenas o JSON como resposta.
                            """

                            # Run Gemini analysis synchronously
                            response = asyncio.run(gemini_thread_manager.generate_content(
                                gemini_model,
                                prompt,
                                generation_config={"temperature": 0.7, "max_output_tokens": 1024}
                            ))

                            if response.prompt_feedback and response.prompt_feedback.block_reason:
                                analysis['text_analysis']['error'] = f'Conteúdo bloqueado: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}'
                            elif response.text:
                                cleaned_response = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                                analysis['text_analysis'] = json.loads(cleaned_response)
                            else:
                                analysis['text_analysis']['error'] = 'Resposta vazia da IA'
                        else:
                            analysis['text_analysis'].update({
                                'risk_level': 'Não Analisável',
                                'summary': 'Texto extraído muito curto para análise.'
                            })
                    else:
                        analysis['text_analysis'].update({
                            'risk_level': 'Indeterminado',
                            'summary': f'Falha na extração de texto: {ocr_results.get("error", "Erro desconhecido")}'
                        })

                except Exception as e:
                    logger.error(f"process_analysis: Image analysis error: {e}", exc_info=True)
                    analysis['text_analysis']['error'] = f'Erro no processamento da imagem: {str(e)}'

            else:
                flash('Nenhum conteúdo fornecido para análise.', 'warning')
                return redirect(url_for('main.index'))

            # Render results template with analysis data
            return render_template('results.html', submission=submission, analysis=analysis)

        except Exception as e:
            logger.error(f"process_analysis: Unexpected error: {e}", exc_info=True)
            flash(f'Erro inesperado: {str(e)}', 'error')
            return redirect(url_for('main.index'))

    except Exception as e:
        logger.error(f"process_analysis: Unexpected error: {e}", exc_info=True)
        flash(f'Erro inesperado: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@main.route('/sobre')
def sobre():
    """Render the about page."""
    try:
        return render_template('sobre.html')
    except Exception as e:
        logger.error("sobre.failed", error=str(e))
        return render_template('errors/500.html'), 500

@main.route('/golpes-recentes')
def golpes_recentes():
    """Render the recent scams page."""
    try:
        return render_template('golpes_recentes.html')
    except Exception as e:
        logger.error("golpes_recentes.failed", error=str(e))
        return render_template('errors/500.html'), 500

@main.route('/dicas-seguranca')
def dicas_seguranca():
    """Render the security tips page."""
    try:
        return render_template('dicas_seguranca.html')
    except Exception as e:
        logger.error("dicas_seguranca.failed", error=str(e))
        return render_template('errors/500.html'), 500

@main.route('/denunciar-golpes')
def denunciar_golpes():
    """Render the scam reporting page."""
    try:
        return render_template('denunciar_golpes.html')
    except Exception as e:
        logger.error("denunciar_golpes.failed", error=str(e))
        return render_template('errors/500.html'), 500 