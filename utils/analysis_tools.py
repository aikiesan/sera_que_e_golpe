import os
import re
import magic
import aiohttp
import asyncio
from PIL import Image
import pytesseract
from bs4 import BeautifulSoup
import validators
from urllib.parse import urlparse
import requests
from typing import Dict, List, Tuple, Optional
import platform
import io
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import json

logger = logging.getLogger(__name__)

class AnalysisTools:
    def __init__(self):
        self.google_safe_browsing_key = os.getenv('GOOGLE_SAFE_BROWSING_KEY')
        
        # Configuração do Gemini
        # We assume genai is already configured by app.py before this class is instantiated.
        # If not, the model initialization will fail, which is an acceptable error.
        try:
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Modelo Gemini Flash (gemini-1.5-flash) referenciado com sucesso em AnalysisTools.")
        except Exception as e:
            logger.error(f"Erro ao referenciar/inicializar modelo Gemini em AnalysisTools: {str(e)}")
            logger.error("Certifique-se que a API do Google Gemini foi configurada globalmente (em app.py) antes de instanciar AnalysisTools.")
            self.model = None
        
        if platform.system() == 'Windows':
            tesseract_path_env = os.getenv('TESSERACT_PATH')
            if tesseract_path_env and os.path.exists(tesseract_path_env):
                 pytesseract.pytesseract.tesseract_cmd = tesseract_path_env
                 logger.info(f"Tesseract path set from TESSERACT_PATH: {tesseract_path_env}")
            else:
                default_tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
                if os.path.exists(default_tesseract_path):
                    pytesseract.pytesseract.tesseract_cmd = default_tesseract_path
                    logger.info(f"Tesseract path set to default: {default_tesseract_path}")
                else:
                    logger.warning("Tesseract not found at default location or via TESSERACT_PATH. Please install Tesseract or set TESSERACT_PATH.")

    async def analyze_text_with_gemini(self, text: str) -> Dict:
        """Analisa texto usando o Gemini Flash. Usado internamente por AnalysisTools."""
        if not self.model:
            logger.warning("AnalysisTools: Modelo Gemini não está configurado, não pode analisar texto.")
            return {'error': 'Modelo Gemini não está configurado em AnalysisTools', 'risk_level': 'Indeterminado'}

        if not text or len(text.strip()) < 10: # Basic check for empty or too short text
            logger.info(f"Texto muito curto ou vazio para análise Gemini em AnalysisTools: '{text[:20]}...'")
            return {
                'risk_level': 'Não Analisável', 
                'summary': 'Texto extraído muito curto ou vazio para análise significativa.',
                'alerts': [],
                'recommendation': 'Verifique a imagem/documento manualmente.'
            }

        try:
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
                "max_output_tokens": 1024,
            }

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

            response = await self.model.generate_content_async(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                reason = getattr(response.prompt_feedback.block_reason, 'name', str(response.prompt_feedback.block_reason))
                logger.error(f"AnalysisTools: Prompt blocked. Reason: {reason}")
                return {'error': f'Análise de texto bloqueada ({reason})', 'risk_level': 'Indeterminado'}

            if not response.candidates:
                logger.error("AnalysisTools: No candidates in response.")
                return {'error': 'Sem candidatos na resposta da IA', 'risk_level': 'Indeterminado'}

            candidate = response.candidates[0]

            # Get the FinishReason enum type from the instance
            FinishReasonEnumType = type(candidate.finish_reason)

            # Compare using the dynamically obtained enum type
            if candidate.finish_reason != FinishReasonEnumType.STOP and \
               candidate.finish_reason != FinishReasonEnumType.MAX_TOKENS:
                reason = getattr(candidate.finish_reason, 'name', str(candidate.finish_reason))
                logger.error(f"AnalysisTools: Abnormal finish reason: {reason}. Ratings: {candidate.safety_ratings}")
                return {'error': f'Análise de texto interrompida ({reason})', 'risk_level': 'Indeterminado', 'summary': f'Interrupção: {reason}'}

            if not candidate.content or not candidate.content.parts or not candidate.content.parts[0].text:
                logger.error("AnalysisTools: Empty content part in response.")
                return {'error': 'Resposta vazia da IA', 'risk_level': 'Indeterminado'}

            generated_text = candidate.content.parts[0].text
            cleaned_response_text = generated_text.strip()
            if cleaned_response_text.startswith("```json"):
                cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
            
            return json.loads(cleaned_response_text)

        except json.JSONDecodeError as e:
            raw_resp_text = generated_text if 'generated_text' in locals() else "N/A"
            logger.error(f"AnalysisTools: Erro ao decodificar JSON da análise: {str(e)}. Raw: {raw_resp_text}")
            return {'error': f'Erro ao decodificar JSON: {str(e)}', 'raw_response': raw_resp_text, 'risk_level': 'Indeterminado'}
        except Exception as e:
            logger.error(f"AnalysisTools: Erro ao analisar texto com Gemini: Type: {type(e)}, Args: {e.args}, Message: {str(e)}")
            return {'error': f'Erro ao analisar texto: {str(e)}', 'risk_level': 'Indeterminado'}

    async def analyze_image(self, image_data: bytes) -> Dict:
        """
        Analyze an image for text content using OCR.
        Does NOT call Gemini; returns extracted text for app.py to handle.
        """
        results = {
            'extracted_text': '',
            'urls_found': [],
            'error': None
        }
        
        try:
            logger.info("AnalysisTools: Analyzing image data for OCR...")
            image = Image.open(io.BytesIO(image_data))
            logger.info("AnalysisTools: Image opened with PIL.")
            
            try:
                available_langs = []
                try:
                    available_langs = pytesseract.get_languages(config='')
                except pytesseract.TesseractError as te:
                    logger.warning(f"Pytesseract could not get languages: {te}")

                if 'por' in available_langs and 'eng' in available_langs:
                    lang_to_use = 'por+eng'
                elif 'por' in available_langs:
                    lang_to_use = 'por'
                elif 'eng' in available_langs:
                    lang_to_use = 'eng'
                else: 
                    lang_to_use = 'eng'
                    if not available_langs:
                        logger.warning(f"Could not detect Tesseract languages. Falling back to '{lang_to_use}'.")
                    else:
                        logger.warning(f"Portuguese ('por') not found in Tesseract languages ({available_langs}). Using '{lang_to_use}'.")
            except Exception as lang_e:
                lang_to_use = 'por+eng' 
                logger.warning(f"Error determining Tesseract languages: {lang_e}. Defaulting to 'por+eng'.")

            extracted_text = pytesseract.image_to_string(image, lang=lang_to_use) 
            results['extracted_text'] = extracted_text.strip()
            logger.info(f"AnalysisTools: OCR Extracted text (first 100 chars): {results['extracted_text'][:100]}")
            
            if results['extracted_text']:
                urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 
                                extracted_text)
                results['urls_found'].extend(urls)
                logger.info(f"AnalysisTools: URLs found in OCRed image text: {urls}")

        except pytesseract.TesseractNotFoundError:
            error_msg = "Tesseract (OCR) não está instalado ou configurado corretamente. A extração de texto de imagem falhou."
            logger.error(error_msg)
            results['error'] = error_msg
            results['extracted_text'] = "[ERRO OCR: Tesseract não encontrado ou não configurado]"
        except pytesseract.TesseractError as te:
            error_msg = f"Erro do Tesseract OCR: {str(te)}. Verifique se os pacotes de idioma (ex: 'por', 'eng') estão instalados."
            logger.error(error_msg, exc_info=True)
            results['error'] = error_msg
            results['extracted_text'] = f"[ERRO OCR: {str(te)}]"
        except Exception as e:
            error_msg = f"Erro ao processar imagem com OCR: {str(e)}"
            logger.error(error_msg, exc_info=True)
            results['error'] = error_msg
            results['extracted_text'] = "[ERRO OCR: Falha ao processar imagem]"
        
        return results

    async def analyze_urls(self, urls: List[str]) -> Dict:
        """
        Analyze a list of URLs for safety using Google Safe Browsing API.
        """
        results = {
            'url_analysis': [], # Will store detailed analysis for each URL
            'suspicious_urls_detected': [] # Will store only URLs flagged as suspicious
        }

        if not self.google_safe_browsing_key:
            logger.warning("Google Safe Browsing API key not configured. URL safety checks will be skipped.")
            for url_item in urls:
                url = str(url_item)
                results['url_analysis'].append({
                    'url': url,
                    'is_safe': None, # Undetermined
                    'status_message': 'Safe Browsing check skipped (API key missing).',
                    'threat_types': [],
                    'details': 'API key for Google Safe Browsing is not configured.'
                })
            return results

        # The Safe Browsing API v4 lookup endpoint
        api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={self.google_safe_browsing_key}"

        async with aiohttp.ClientSession() as session:
            for url_item in urls:
                url = str(url_item) # Defensive casting
                analysis_entry = {
                    'url': url,
                    'is_safe': None, # True (safe), False (unsafe), None (error/undetermined)
                    'status_message': 'Pending check',
                    'threat_types': [],
                    'details': ''
                }

                if not validators.url(url):
                    analysis_entry['is_safe'] = False
                    analysis_entry['status_message'] = 'Invalid URL format.'
                    analysis_entry['details'] = 'The provided string is not a valid URL.'
                    results['url_analysis'].append(analysis_entry)
                    if url not in results['suspicious_urls_detected']:
                        results['suspicious_urls_detected'].append(url)
                    continue

                payload = {
                    "client": {
                        "clientId": "seraquegolpe-app",
                        "clientVersion": "1.0.0"
                    },
                    "threatInfo": {
                        "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
                        "platformTypes": ["ANY_PLATFORM"],
                        "threatEntryTypes": ["URL"],
                        "threatEntries": [
                            {"url": url}
                        ]
                    }
                }

                try:
                    # Using aiohttp for async HTTP requests
                    async with session.post(api_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        response.raise_for_status()
                        sb_data = await response.json()

                        if sb_data and 'matches' in sb_data:
                            analysis_entry['is_safe'] = False
                            analysis_entry['status_message'] = 'Potentially unsafe URL detected.'
                            for match in sb_data['matches']:
                                threat_type = match.get('threatType', 'UNKNOWN')
                                analysis_entry['threat_types'].append(threat_type)
                                analysis_entry['details'] += f"Threat: {threat_type}. "
                            if url not in results['suspicious_urls_detected']:
                                results['suspicious_urls_detected'].append(url)
                        else:
                            analysis_entry['is_safe'] = True
                            analysis_entry['status_message'] = 'No threats found by Google Safe Browsing.'
                            analysis_entry['details'] = 'This URL is not currently listed as unsafe.'

                except aiohttp.ClientResponseError as http_err:
                    error_message = f"HTTP error during Safe Browsing check: {http_err}"
                    logger.error(error_message)
                    analysis_entry['is_safe'] = None # Undetermined due to error
                    analysis_entry['status_message'] = 'Error during Safe Browsing check (HTTP).'
                    analysis_entry['details'] = str(http_err)
                except aiohttp.ClientError as client_err:
                    logger.error(f"Client error during Safe Browsing check: {client_err}")
                    analysis_entry['is_safe'] = None # Undetermined
                    analysis_entry['status_message'] = 'Error during Safe Browsing check (Network/Request).'
                    analysis_entry['details'] = str(client_err)
                except asyncio.TimeoutError:
                    logger.error(f"Timeout during Safe Browsing check for {url}")
                    analysis_entry['is_safe'] = None
                    analysis_entry['status_message'] = 'Safe Browsing check timed out.'
                    analysis_entry['details'] = 'The request to Google Safe Browsing API timed out.'
                except Exception as e:
                    logger.error(f"Unexpected error during Safe Browsing check for {url}: {e}", exc_info=True)
                    analysis_entry['is_safe'] = None # Undetermined
                    analysis_entry['status_message'] = 'Unexpected error during Safe Browsing check.'
                    analysis_entry['details'] = str(e)
                
                results['url_analysis'].append(analysis_entry)
        
        return results

    async def verify_document(self, file_data: bytes) -> Dict:
        results = {
            'file_type': 'Desconhecido',
            'text_content': None, 
            'extracted_text': None, 
            'urls_found': [],
            'suspicious_elements': [],
            'warnings': [],
            'error': None,
            'gemini_analysis': None 
        }
        
        try:
            mime_type = magic.from_buffer(file_data, mime=True)
            results['file_type'] = mime_type
            logger.info(f"AnalysisTools: Verifying document. Detected MIME type: {mime_type}")
            
            if 'pdf' in mime_type:
                results['warnings'].append('A extração de texto de PDFs é limitada. Para melhor análise, envie prints de tela do conteúdo do PDF.')
                results['text_content'] = "[Conteúdo PDF não extraído diretamente nesta versão. Considere analisar prints.]"
                logger.info("AnalysisTools: PDF document detected. Direct text extraction not robustly implemented.")
            
            elif 'image' in mime_type: 
                logger.info("AnalysisTools: Document is an image, analyzing with analyze_image...")
                image_analysis_results = await self.analyze_image(file_data)
                results.update(image_analysis_results) 
                if image_analysis_results.get('error'):
                    results['error'] = image_analysis_results['error']
            
            elif 'text' in mime_type or 'opendocument.text' in mime_type or 'wordprocessingml.document' in mime_type:
                try:
                    if 'text/plain' in mime_type:
                        results['text_content'] = file_data.decode('utf-8', errors='replace').strip()
                    else:
                        results['text_content'] = "[Extração de texto para este tipo de documento complexo não implementada. Tente com um print screen.]"
                        results['warnings'].append(f"Extração direta de {mime_type} não suportada. Use prints se possível.")

                    logger.info(f"AnalysisTools: Text-based document content (first 100 chars): {str(results['text_content'])[:100]}")
                    
                    if results['text_content'] and not results['text_content'].startswith("["):
                        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', 
                                        results['text_content'])
                        results['urls_found'].extend(urls)
                        logger.info(f"AnalysisTools: URLs found in text document: {urls}")
                        
                        if self.model:
                            logger.info("AnalysisTools: Analyzing extracted document text with its own Gemini model...")
                            results['gemini_analysis'] = await self.analyze_text_with_gemini(results['text_content'])
                            
                except UnicodeDecodeError:
                    err_msg = "Não foi possível decodificar o arquivo de texto (provavelmente não é UTF-8 puro)."
                    results['error'] = err_msg
                    results['text_content'] = f"[{err_msg}]"
                    logger.warning(err_msg)
            
            else:
                warn_msg = f"Tipo de arquivo não suportado para extração de conteúdo automática: {mime_type}. Tente com um print screen."
                results['warnings'].append(warn_msg)
                results['text_content'] = f"[{warn_msg}]"
                logger.info(warn_msg)

        except Exception as e:
            error_msg = f"Erro ao processar documento: {str(e)}"
            results['error'] = error_msg
            logger.error(error_msg, exc_info=True)
        
        return results