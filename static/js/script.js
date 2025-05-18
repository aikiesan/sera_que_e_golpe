document.addEventListener('DOMContentLoaded', () => {
    // Function to get CSRF token from hidden input
    function getCsrfToken() {
        const csrfInput = document.querySelector('input[name="csrf_token"]');
        if (csrfInput) {
            return csrfInput.value;
        }
        console.error('CSRF token input not found!');
        return null;
    }

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
        if (data.error) {
            imageOcrErrorEl.textContent = `Erro: ${data.error}`;
            imageOcrErrorEl.style.display = 'block';
            imageGeminiAnalysisSection.style.display = 'none';
        } else {
            imageOcrErrorEl.style.display = 'none';
        }

        if (data.text_analysis) {
            if (data.text_analysis.error) {
                imageGeminiErrorEl.textContent = `Erro na análise: ${data.text_analysis.error}`;
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
        } else {
            imageGeminiAnalysisSection.style.display = 'none';
            imageGeminiErrorEl.textContent = 'Análise não disponível.';
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

            const csrfToken = getCsrfToken();
            if (!csrfToken) {
                showLoading(false);
                displayError('Erro de segurança (CSRF). Recarregue a página.');
                return;
            }

            try {
                const response = await fetch('/api/verificar', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
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
                displayError(error.message || 'Erro ao processar a requisição.');
            }
        });
    }

    // Event listener para o formulário de imagem
    if (imageUploadForm) {
        imageUploadForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const file = imageFileInput.files[0];
            if (!file) {
                displayError('Por favor, selecione uma imagem para análise.');
                imageFileInput.focus();
                return;
            }

            showLoading(true);

            const csrfToken = getCsrfToken();
            if (!csrfToken) {
                showLoading(false);
                displayError('Erro de segurança (CSRF). Recarregue a página.');
                return;
            }

            const formData = new FormData(imageUploadForm);
            formData.append('csrf_token', csrfToken);

            try {
                // Use the form's action URL if available, fallback to hardcoded URL
                const uploadUrl = imageUploadForm.action || '/api/analyze_image_api';
                const response = await fetch(uploadUrl, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken
                    },
                    body: formData
                });

                showLoading(false);
                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || `Erro HTTP: ${response.status}`);
                }
                populateImageAnalysisResults(data);

            } catch (error) {
                showLoading(false);
                displayError(error.message || 'Erro ao processar a imagem.');
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

    // Text analysis form handling
    const textForm = document.getElementById('text-analysis-form');
    const charCounter = document.getElementById('char-count');

    if (messageInput) {
        messageInput.addEventListener('input', function() {
            const length = this.value.length;
            charCounter.textContent = length;
            
            // Visual feedback when approaching limit
            const counter = document.querySelector('.char-counter');
            if (length > 4500) {
                counter.classList.add('near-limit');
            } else {
                counter.classList.remove('near-limit');
            }
        });
    }

    if (textForm) {
        textForm.addEventListener('submit', function(e) {
            const message = messageInput.value.trim();
            if (!message) {
                e.preventDefault();
                alert('Por favor, insira uma mensagem para análise.');
                messageInput.focus();
                return;
            }

            // Show loading state
            const button = this.querySelector('button[type="submit"]');
            const buttonText = button.querySelector('.button-text');
            const spinner = button.querySelector('.spinner');
            
            buttonText.style.display = 'none';
            spinner.style.display = 'inline-block';
            button.disabled = true;
        });
    }

    // Image analysis form handling
    const imageForm = document.getElementById('image-analysis-form');
    const imageInput = document.getElementById('image-file-input');
    const preview = document.getElementById('image-preview');
    const fileName = document.getElementById('file-name');

    if (imageInput) {
        imageInput.addEventListener('change', function() {
            const file = this.files[0];
            
            if (file) {
                // Validate file type
                const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
                if (!validTypes.includes(file.type)) {
                    alert('Por favor, selecione apenas arquivos PNG, JPEG ou WebP.');
                    this.value = '';
                    preview.style.display = 'none';
                    fileName.textContent = 'Nenhum arquivo selecionado';
                    return;
                }
                
                // Validate file size (5MB)
                if (file.size > 5 * 1024 * 1024) {
                    alert('O arquivo é muito grande. Por favor, selecione um arquivo menor que 5MB.');
                    this.value = '';
                    preview.style.display = 'none';
                    fileName.textContent = 'Nenhum arquivo selecionado';
                    return;
                }
                
                fileName.textContent = file.name;
                
                // Create preview
                const reader = new FileReader();
                reader.onload = function(e) {
                    preview.src = e.target.result;
                    preview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            } else {
                preview.style.display = 'none';
                fileName.textContent = 'Nenhum arquivo selecionado';
            }
        });
    }

    if (imageForm) {
        imageForm.addEventListener('submit', function(e) {
            const file = imageInput.files[0];
            if (!file) {
                e.preventDefault();
                alert('Por favor, selecione uma imagem para análise.');
                imageInput.focus();
                return;
            }

            // Show loading state
            const button = this.querySelector('button[type="submit"]');
            const buttonText = button.querySelector('.button-text');
            const spinner = button.querySelector('.spinner');
            
            buttonText.style.display = 'none';
            spinner.style.display = 'inline-block';
            button.disabled = true;
        });
    }

    // Flash message handling
    const closeButtons = document.querySelectorAll('.close-alert');
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            this.parentElement.style.display = 'none';
        });
    });

    // Tutorial modal handling
    const modal = document.getElementById('tutorial-modal');
    const openButton = document.getElementById('open-tutorial');
    const closeButton = document.querySelector('.close');

    if (modal && openButton && closeButton) {
        openButton.onclick = function() {
            modal.style.display = 'block';
        }

        closeButton.onclick = function() {
            modal.style.display = 'none';
        }

        window.onclick = function(event) {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        }
    }

    // Form submission handling with loading states
    document.querySelectorAll('.analysis-form').forEach(form => {
        form.addEventListener('submit', function(e) {
            // Get CSRF token
            const csrfToken = getCsrfToken();
            if (!csrfToken) {
                e.preventDefault();
                alert('Erro de segurança (CSRF). Por favor, recarregue a página.');
                return;
            }

            // Add CSRF token to form if not present
            let csrfInput = form.querySelector('input[name="csrf_token"]');
            if (!csrfInput) {
                csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                csrfInput.value = csrfToken;
                form.appendChild(csrfInput);
            }

            // Show loading state
            const button = this.querySelector('button[type="submit"]');
            const buttonText = button.querySelector('.button-text');
            const spinner = button.querySelector('.spinner');
            
            buttonText.style.display = 'none';
            spinner.style.display = 'inline-block';
            button.disabled = true;
        });
    });
});