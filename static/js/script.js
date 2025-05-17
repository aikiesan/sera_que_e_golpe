document.addEventListener('DOMContentLoaded', () => {
    const scamForm = document.getElementById('scam-form');
    const messageInput = document.getElementById('message-input');
    
    const imageUploadForm = document.getElementById('image-upload-form');
    const imageFileInput = document.getElementById('image-file-input');

    const resultSection = document.getElementById('result-section');
    const resultTextAnalysis = document.getElementById('text-analysis-result');
    const resultImageAnalysis = document.getElementById('image-analysis-result');
    
    const riskLevelEl = document.getElementById('risk-level');
    const summaryEl = document.getElementById('summary');
    const alertsListEl = document.getElementById('alerts-list');
    const recommendationEl = document.getElementById('recommendation');
    const fullAnalysisDetailsEl = document.getElementById('full-analysis-details');
    const analysisDetailsToggle = document.getElementById('analysis-details-toggle');

    const imageExtractedTextEl = document.getElementById('image-extracted-text');
    const imageOcrErrorEl = document.getElementById('image-ocr-error');
    const imageGeminiAnalysisSection = document.getElementById('image-gemini-analysis-section');
    const imageRiskLevelEl = document.getElementById('image-risk-level');
    const imageSummaryEl = document.getElementById('image-summary');
    const imageAlertsListEl = document.getElementById('image-alerts-list');
    const imageRecommendationEl = document.getElementById('image-recommendation');
    const imageGeminiErrorEl = document.getElementById('image-gemini-error');

    const loadingIndicator = document.getElementById('loading-indicator');
    const loadingGif = document.getElementById('loading-gif');
    const errorMessageEl = document.getElementById('error-message');

    const tutorialModal = document.getElementById('tutorial-modal');
    const openTutorialButton = document.getElementById('open-tutorial');
    const closeTutorialButton = tutorialModal.querySelector('.close-button');

    // Função para mostrar/esconder loading
    function showLoading(isLoading) {
        if (isLoading) {
            loadingIndicator.style.display = 'block';
            if(loadingGif) loadingGif.style.display = 'inline-block';
            resultSection.style.display = 'none';
            errorMessageEl.style.display = 'none';
            resultTextAnalysis.style.display = 'none';
            resultImageAnalysis.style.display = 'none';
        } else {
            loadingIndicator.style.display = 'none';
            if(loadingGif) loadingGif.style.display = 'none';
        }
    }

    // Função para mostrar erros gerais
    function displayError(message) {
        errorMessageEl.textContent = `Erro: ${message}`;
        errorMessageEl.style.display = 'block';
        resultSection.style.display = 'block';
        resultTextAnalysis.style.display = 'none';
        resultImageAnalysis.style.display = 'none';
    }
    
    // Função para resetar e popular resultados de análise de texto
    function populateTextAnalysisResults(data) {
        riskLevelEl.textContent = data.risk_level || 'Indeterminado';
        summaryEl.textContent = data.summary || 'Nenhuma informação.';
        recommendationEl.textContent = data.recommendation || 'Verifique com cuidado.';
        
        alertsListEl.innerHTML = '';
        if (data.alerts && data.alerts.length > 0) {
            data.alerts.forEach(alertText => {
                const li = document.createElement('li');
                li.textContent = alertText;
                alertsListEl.appendChild(li);
            });
        } else {
            const li = document.createElement('li');
            li.textContent = 'Nenhum alerta específico.';
            alertsListEl.appendChild(li);
        }

        // Cor do nível de risco
        riskLevelEl.className = 'risk-placeholder';
        if (data.risk_level) {
            const riskClass = `risk-${data.risk_level.toLowerCase().replace(/\s+/g, '-')}`;
            riskLevelEl.classList.add(riskClass);
        }
        
        // Detalhes completos (opcional)
        if (data.analysis_details) {
            analysisDetailsToggle.style.display = 'block';
            fullAnalysisDetailsEl.textContent = JSON.stringify(data, null, 2);
        } else {
            analysisDetailsToggle.style.display = 'none';
        }

        resultTextAnalysis.style.display = 'block';
        resultImageAnalysis.style.display = 'none';
        resultSection.style.display = 'block';
    }

    // Função para resetar e popular resultados de análise de imagem
    function populateImageAnalysisResults(data) {
        imageExtractedTextEl.textContent = data.extracted_text || '[Nenhum texto extraído ou erro na extração]';
        
        if (data.error && !data.extracted_text) {
            imageOcrErrorEl.textContent = `Erro OCR: ${data.error}`;
            imageOcrErrorEl.style.display = 'block';
            imageGeminiAnalysisSection.style.display = 'none';
        } else {
            imageOcrErrorEl.style.display = 'none';
        }

        if (data.text_analysis) {
            if (data.text_analysis.error) {
                imageGeminiErrorEl.textContent = `Erro na análise da IA: ${data.text_analysis.error}`;
                imageGeminiErrorEl.style.display = 'block';
                imageGeminiAnalysisSection.style.display = 'none';
            } else {
                imageGeminiErrorEl.style.display = 'none';
                imageGeminiAnalysisSection.style.display = 'block';
                imageRiskLevelEl.textContent = data.text_analysis.risk_level || 'Indeterminado';
                imageSummaryEl.textContent = data.text_analysis.summary || 'Nenhuma informação.';
                imageRecommendationEl.textContent = data.text_analysis.recommendation || 'Verifique com cuidado.';

                imageAlertsListEl.innerHTML = '';
                if (data.text_analysis.alerts && data.text_analysis.alerts.length > 0) {
                    data.text_analysis.alerts.forEach(alertText => {
                        const li = document.createElement('li');
                        li.textContent = alertText;
                        imageAlertsListEl.appendChild(li);
                    });
                } else {
                     const li = document.createElement('li');
                     li.textContent = 'Nenhum alerta específico.';
                     imageAlertsListEl.appendChild(li);
                }
                
                imageRiskLevelEl.className = 'risk-placeholder';
                if (data.text_analysis.risk_level) {
                    const riskClass = `risk-${data.text_analysis.risk_level.toLowerCase().replace(/\s+/g, '-')}`;
                    imageRiskLevelEl.classList.add(riskClass);
                }
            }
        } else if (data.extracted_text) {
            imageGeminiAnalysisSection.style.display = 'block';
            imageGeminiErrorEl.textContent = 'Análise do texto pela IA não disponível ou não realizada.';
            imageGeminiErrorEl.style.display = 'block';
        }

        resultImageAnalysis.style.display = 'block';
        resultTextAnalysis.style.display = 'none';
        resultSection.style.display = 'block';
    }

    // Event listener para o formulário de texto
    if (scamForm) {
        scamForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const message = messageInput.value.trim();
            if (!message) {
                displayError('Por favor, insira uma mensagem para análise.');
                messageInput.focus();
                return;
            }

            showLoading(true);

            try {
                const response = await fetch('/verificar', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message }),
                });

                showLoading(false);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || data.summary || `Erro HTTP: ${response.status}`);
                }
                populateTextAnalysisResults(data);

            } catch (error) {
                showLoading(false);
                console.error('Erro ao verificar mensagem:', error);
                displayError(error.message || 'Não foi possível conectar ao servidor ou processar a resposta.');
            }
        });
    }

    // Event listener para o formulário de upload de imagem
    if (imageUploadForm) {
        imageUploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const imageFile = imageFileInput.files[0];

            if (!imageFile) {
                displayError('Por favor, selecione um arquivo de imagem.');
                return;
            }

            showLoading(true);
            const formData = new FormData();
            formData.append('image', imageFile);

            try {
                const response = await fetch('/analyze_image', {
                    method: 'POST',
                    body: formData,
                });

                showLoading(false);
                const data = await response.json();

                if (!response.ok) {
                     throw new Error(data.error || `Erro HTTP: ${response.status}`);
                }
                populateImageAnalysisResults(data);

            } catch (error) {
                showLoading(false);
                console.error('Erro ao analisar imagem:', error);
                displayError(error.message || 'Não foi possível conectar ao servidor ou processar a resposta da imagem.');
            }
        });
    }

    // Lógica do Modal de Tutorial
    if (openTutorialButton && tutorialModal && closeTutorialButton) {
        openTutorialButton.addEventListener('click', (e) => {
            e.preventDefault();
            tutorialModal.style.display = 'block';
        });
        closeTutorialButton.addEventListener('click', () => {
            tutorialModal.style.display = 'none';
        });
        window.addEventListener('click', (event) => {
            if (event.target === tutorialModal) {
                tutorialModal.style.display = 'none';
            }
        });
    } else {
        console.warn("Elementos do modal do tutorial não encontrados.");
    }
});