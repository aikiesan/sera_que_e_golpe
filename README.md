# Documentação do Projeto: "Será Que é Golpe?" - Verificador de Mensagens Suspeitas

**Versão:** 0.1.0 (Protótipo de Competição - 24h)
**Data:** [Insira a Data Atual]
**Autor:** [Seu Nome/Nome da Equipe]
**Tecnologias Principais:** Python (Flask), Google Gemini API, HTML, CSS, JavaScript

## 1. Visão Geral do Projeto

"Será Que é Golpe?" é uma aplicação web projetada para ajudar usuários, com foco especial no público idoso, a identificar rapidamente se uma mensagem de texto (SMS, WhatsApp, etc.) recebida é potencialmente um golpe ou fraude. A ferramenta utiliza o poder da API do Google Gemini para analisar o conteúdo da mensagem e fornecer uma avaliação clara e compreensível, juntamente com justificativas. A interface busca ser extremamente simples e acessível, priorizando a facilidade de uso através do método de copiar e colar mensagens.

## 2. Objetivo Principal

O objetivo central é fornecer uma primeira linha de defesa contra golpes digitais que frequentemente visam indivíduos menos familiarizados com táticas de phishing e engenharia social. A ferramenta visa empoderar os usuários a tomarem decisões mais informadas antes de clicarem em links suspeitos, fornecerem dados pessoais ou realizarem transações financeiras induzidas por mensagens fraudulentas.

## 3. Funcionalidades Chave (Protótipo)

1.  **Interface de Entrada de Mensagem:**
    *   Um campo de texto (textarea) grande e واضح onde o usuário pode colar a mensagem suspeita que recebeu.
2.  **Análise de Mensagem com Google Gemini:**
    *   Após o usuário submeter a mensagem, o texto é enviado para um backend Python (Flask).
    *   O backend interage com a API do Google Gemini, enviando a mensagem para análise.
    *   **(Opcional/Visão Futura - "Tool Use")** O sistema pode ser instruído a usar "ferramentas" através do Gemini para:
        *   Verificar a reputação de URLs encontradas na mensagem (ex: via Google Safe Browsing ou busca na web).
        *   Buscar informações sobre números de telefone mencionados.
3.  **Exibição de Resultados:**
    *   O resultado da análise do Gemini é exibido de forma clara na interface web, utilizando:
        *   **Indicadores Visuais:** Cores (ex: Vermelho para "Alto Risco de Golpe", Amarelo para "Atenção/Suspeito", Verde para "Baixo Risco").
        *   **Linguagem Simples:** Um resumo conciso da avaliação (ex: "CUIDADO: Parece um golpe!", "FIQUE ATENTO!", "PARECE SEGURO, MAS VERIFIQUE").
        *   **Justificativa:** Pontos chave identificados pelo Gemini que levaram àquela conclusão (ex: "A mensagem pede dados bancários", "O link parece ser falso", "Promessa de prêmio muito grande e inesperada").
4.  **Tutorial de Copiar e Colar:**
    *   Uma seção de ajuda visual (imagens estáticas ou GIFs) integrada à página, explicando passo a passo como copiar uma mensagem de aplicativos comuns (WhatsApp, SMS) e colá-la na ferramenta. Este tutorial é crucial para a acessibilidade do público-alvo.

## 4. Arquitetura da Solução (Protótipo)

*   **Frontend:**
    *   **HTML:** Estrutura da página web.
    *   **CSS:** Estilização para usabilidade e clareza visual.
    *   **JavaScript:** Captura da mensagem do `textarea`, envio para o backend via `fetch` API, e exibição dinâmica dos resultados recebidos.
*   **Backend:**
    *   **Python (Flask):** Microframework web para:
        *   Servir a página HTML principal.
        *   Prover um endpoint de API (`/verificar_golpe`) para receber o texto da mensagem.
        *   Orquestrar a comunicação com a API do Google Gemini.
        *   Processar a resposta do Gemini e retorná-la ao frontend.
*   **API Externa:**
    *   **Google Gemini API:** Núcleo da inteligência de análise de texto.

## 5. Fluxo do Usuário

1.  O usuário recebe uma mensagem que considera suspeita em seu celular (SMS, WhatsApp, etc.).
2.  O usuário acessa a aplicação web "Será Que é Golpe?".
3.  Caso não saiba como copiar a mensagem, o usuário consulta o tutorial "Como copiar e colar?" disponível na página.
4.  O usuário copia a mensagem do seu aplicativo de mensagens.
5.  O usuário cola a mensagem copiada no campo de texto da aplicação "Será Que é Golpe?".
6.  O usuário clica no botão "VERIFICAR MENSAGEM".
7.  A mensagem é enviada ao backend, que a repassa para a API do Google Gemini.
8.  A API do Gemini analisa a mensagem.
9.  O resultado da análise é retornado ao backend e, em seguida, ao frontend.
10. A aplicação exibe o resultado de forma clara e visual para o usuário, indicando o nível de risco e os motivos.

## 6. Considerações de Usabilidade para o Público Idoso

*   **Simplicidade Extrema:** Mínimo de botões e opções.
*   **Fontes Grandes e Legíveis:** Alto contraste de cores.
*   **Instruções Claras e Diretas:** Linguagem simples, evitando jargões técnicos.
*   **Foco no Copiar/Colar:** O método de entrada principal é facilitado por um tutorial detalhado.
*   **Feedback Imediato e Compreensível:** Resultados da análise devem ser fáceis de entender rapidamente.

## 7. Limitações do Protótipo (24h)

*   Não é um aplicativo móvel nativo instalável.
*   O tutorial de copiar/colar é informativo (imagens/GIFs) e não interativo dentro do sistema operacional.
*   Funcionalidades avançadas de "tool use" com o Gemini podem ser implementadas de forma básica ou apenas conceitualizadas.
*   Não possui persistência de dados ou contas de usuário.
*   A estilização será funcional, mas não exaustivamente polida.

## 8. Próximos Passos (Pós-Competição / Evolução do Projeto)

*   Desenvolvimento de um aplicativo móvel nativo (Android e/ou iOS) para melhor integração e acessibilidade.
*   Implementação de métodos de entrada alternativos (ex: leitura de mensagem por voz, análise de print de tela).
*   Aprimoramento do sistema de agentes/tool use com o Gemini para análises mais profundas.
*   Criação de um banco de dados de golpes conhecidos para complementar a análise da IA.
*   Recursos de educação contínua sobre segurança digital dentro do app.
*   Possibilidade de denúncia anônima de golpes para um sistema de alerta comunitário.

## 9. Como Executar o Protótipo

1.  Certifique-se de ter Python 3.x instalado.
2.  Clone o repositório (ou crie os arquivos conforme estrutura).
3.  Crie e ative um ambiente virtual:
    ```bash
    python -m venv venv
    # Windows CMD:
    venv\Scripts\activate
    # Windows PowerShell:
    # venv\Scripts\Activate.ps1
    # Linux/macOS:
    # source venv/bin/activate
    ```
4.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```
5.  Configure sua API Key do Google Gemini (ex: através de uma variável de ambiente `GOOGLE_API_KEY` ou um arquivo `.env` se estiver usando `python-dotenv`).
6.  Execute o servidor Flask:
    ```bash
    python app.py
    ```
7.  Abra seu navegador e acesse `http://127.0.0.1:5000/` (ou a porta configurada).

---

Este documento serve como um guia inicial para o desenvolvimento e compreensão do protótipo "Será Que é Golpe?".