# 🔎 LeadFinder

> Sistema inteligente de prospecção e qualificação de leads comerciais, desenvolvido para automatizar a descoberta, enriquecimento, análise e priorização de empresas com potencial comercial.

![Status](https://img.shields.io/badge/status-production--ready-success)
![Tests](https://img.shields.io/badge/tests-201%20passed-success)
![Security](https://img.shields.io/badge/security-hardened-blue)
![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red?logo=streamlit)

---

## 📌 Sobre o projeto

O **LeadFinder** é uma aplicação desenvolvida para auxiliar processos de prospecção comercial.

A ideia é transformar uma busca por um determinado tipo de negócio em um conjunto estruturado de leads, utilizando dados públicos para identificar empresas, processar suas informações, calcular um score comercial e gerar dados prontos para abordagem.

O sistema foi desenvolvido com foco não apenas na funcionalidade, mas também em:

- 🔐 Segurança
- 🧩 Modularidade
- 🛡️ Tolerância a falhas
- 📊 Observabilidade
- 📈 Métricas comerciais
- 💾 Integridade de dados
- 🧪 Testes automatizados
- 🚦 Controle de recursos
- 🔄 Graceful Degradation

---

## 🚀 Fluxo da aplicação

```text
                    ┌─────────────────┐
                    │   Parâmetros    │
                    │    da busca     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Geocoding    │
                    │    Nominatim    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Overpass     │
                    │ OpenStreetMap   │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Lead Processor  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     Scoring     │
                    │   Comercial     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     Payload     │
                    │   Comercial     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   Message Gen   │
                    │   LLM / Draft   │
                    └────────┬────────┘
                             │
                             ▼

                             ✨ Funcionalidades
🔍 Busca de empresas

Permite pesquisar empresas por categoria e localização utilizando dados públicos do OpenStreetMap através do Overpass API.

O processo utiliza geocoding para transformar cidade/estado em coordenadas antes da busca geográfica.

🧠 Processamento de Leads

Os dados obtidos são normalizados e transformados em uma estrutura consistente de Lead.

O processamento considera informações como:

Nome
Categoria
Telefone
WhatsApp
E-mail
Website
Instagram
Facebook
Endereço
Cidade
Estado
Coordenadas
Identificador OpenStreetMap
📊 Scoring Comercial

Cada lead recebe uma avaliação baseada em diferentes indicadores comerciais.

Entre os fatores considerados estão:

Presença digital
Disponibilidade de contato
Oportunidade comercial
Qualidade dos dados
Proximidade
Confiabilidade

O sistema também classifica os leads por prioridade, facilitando a identificação das melhores oportunidades.

🤖 Geração de mensagens

O LeadFinder possui uma camada de geração de mensagens comerciais utilizando provedores de IA.

Os provedores são controlados por uma whitelist e existe um modo Draft/Offline para permitir degradação graciosa quando um serviço externo não estiver disponível.

Isso significa que uma falha na IA não precisa interromper todo o processo.

🛡️ Segurança

Segurança foi uma das principais preocupações durante o desenvolvimento.

O projeto passou por diversas etapas de hardening entre as Sprints 7.1 e 7.5.

Proteções implementadas
🔑 Proteção e redaction de secrets
🚫 SSRF mitigation
⏱️ Timeouts explícitos em requisições
📦 Limitação de tamanho de respostas
🚦 Rate limiting
🧵 Proteção contra condições de corrida
🔄 Atomic Commit
🧠 Proteção contra corrupção de Session State
🤖 Fallback para falhas de LLM
🧹 Sanitização de dados
📄 Proteção contra Formula Injection
💾 Limitação do histórico de execução
🧬 Deep Copy para isolamento de estado
🔎 AST/Supply Chain scanning
📊 Observabilidade segura
📈 Observabilidade

Cada execução pode gerar métricas operacionais contendo informações como:

run_id
params
counts
durations
provider
status
failure_reason
commercial_metrics

O sistema também mede individualmente etapas do pipeline, permitindo identificar gargalos entre:

Geocoding
Overpass
Processing
Enrichment
Scoring
Payload
LLM

Além disso, falhas são classificadas através de categorias controladas, evitando exposição de tracebacks ou mensagens potencialmente sensíveis.

📚 Histórico de execuções

O LeadFinder mantém um histórico limitado das últimas execuções.

Características
Limite de 20 execuções
Deep Copy
Estrutura serializável
Atomic Commit
Proteção contra corrupção
Agregação de métricas
Análise de performance
Análise de falhas
Exportação do histórico

O histórico permite acompanhar indicadores como:

Total de leads encontrados
Leads com WhatsApp
Leads com e-mail
Leads sem website
Leads de alta prioridade
Média de leads por execução
Duração das execuções
Principais causas de falha
📤 Exportação

Os leads podem ser exportados para:

CSV
XLSX

A exportação possui um contrato fixo de 28 colunas, garantindo consistência para processos posteriores.

Também existe proteção contra Formula Injection, neutralizando valores iniciados por caracteres que poderiam ser interpretados como fórmulas por softwares de planilha.

Exemplo:

=CMD(...)
@SUM(...)
+1-555...
-AlgumValor

são tratados como texto em vez de fórmulas executáveis.

🧪 Testes

O projeto possui uma suíte de testes automatizados voltada tanto para funcionalidade quanto para segurança.

Estado atual
201 testes
201 passed
0 failed
0 errors
0 skipped

Os testes cobrem:

Pipeline
Scoring
Processamento
Rate limiting
Network failures
HTTP failures
Response bombs
Session State
Atomic Commit
Deep Copy
LLM fallback
Exportação
Formula Injection
Métricas
Histórico
Boundary conditions
AST scanning
Failure paths
End-to-End flows
🏗️ Arquitetura

O projeto utiliza uma arquitetura baseada em serviços, mantendo a lógica de negócio separada da interface.

LeadFinder/
│
├── app.py
│
├── services/
│   ├── overpass.py
│   ├── geocoding.py
│   ├── lead_processor.py
│   ├── lead_scoring.py
│   ├── commercial_payload.py
│   ├── export_service.py
│   └── ...
│
├── tests/
│   ├── test_sprint_7.py
│   ├── test_sprint_7_3.py
│   ├── test_sprint_7_4.py
│   ├── test_sprint_7_5.py
│   └── ...
│
└── README.md

A separação permite que componentes críticos sejam testados de forma isolada sem depender diretamente da interface Streamlit.

🧰 Tecnologias
Tecnologia	Utilização
Python	Backend e lógica principal
Streamlit	Interface da aplicação
Pandas	Manipulação e exportação de dados
OpenPyXL	Geração de XLSX
Requests	Comunicação HTTP
OpenStreetMap	Fonte de dados geográficos
Overpass API	Busca de empresas
Nominatim	Geocoding
unittest	Testes automatizados
AST	Análise estática de segurança
🔐 Princípios de segurança

O projeto segue alguns princípios fundamentais:

Fail Closed

Quando uma dependência externa ou etapa crítica falha, o sistema prefere interromper ou degradar de forma controlada em vez de continuar com dados potencialmente inválidos.

Least Exposure

Logs e métricas evitam armazenar informações desnecessárias, especialmente secrets, tracebacks e payloads potencialmente sensíveis.

Resource Bounding

Operações externas e estruturas de memória possuem limites para evitar consumo descontrolado de recursos.

Isolation

Execuções concorrentes não podem sobrescrever dados de outra execução através do mecanismo de run_id.

Defense in Depth

A segurança não depende de uma única proteção. O projeto combina validação, sanitização, limites, isolamento, testes e análise estática.

📋 Roadmap

O projeto foi estruturado através de Sprints incrementais de desenvolvimento e hardening.

Sprints concluídas
 Pipeline de descoberta de leads
 Processamento e normalização
 Scoring comercial
 Geração de payloads
 Geração de mensagens
 Exportação CSV/XLSX
 Hardening de segurança
 Rate limiting
 Proteção contra Response Bomb
 Atomic Commit
 Failure Paths
 Testes E2E
 Observabilidade
 Métricas comerciais
 Histórico de execuções
 Exportação do histórico
Próximos passos
 Integrações avançadas de LLM
 Melhorias de análise comercial
 Novas fontes de leads
 Evolução do dashboard
 Melhorias de automação de prospecção
⚠️ Observações

O LeadFinder utiliza dados provenientes de serviços públicos e APIs externas. A disponibilidade e qualidade desses dados dependem das fontes utilizadas.

O sistema foi projetado para lidar com indisponibilidade dessas dependências através de timeouts, fallbacks e degradação controlada.

👨‍💻 Autor

Guilherme Ferreira

Desenvolvedor de Software

📍 Guarulhos — SP, Brasil

📧 guilhermeferreira07.dev@gmail.com

⭐ Status do projeto

HARDENED — PRODUCTION READY

Último checkpoint:

Sprint 7.5

201 testes
201 passed
0 failed
0 errors
0 skipped

Desenvolvido com foco em automação, segurança, engenharia de software e inteligência comercial.


### Uma sugestão importante

Eu **não colocaria os códigos completos das Sprints no README**. O relatório que você me mandou é excelente como documentação técnica interna, mas no GitHub o README precisa vender o projeto rapidamente para quem entrar no repositório.

Eu deixaria o README acima como a **porta de entrada** e, depois, poderíamos criar uma estrutura de documentação separada, por exemplo:

```text
docs/
├── ARCHITECTURE.md
├── SECURITY.md
├── TESTING.md
├── SPRINTS.md
└── ROADMAP.md
                    ┌─────────────────┐
                    │ Exportação CSV  │
                    │      / XLSX     │
                    └─────────────────┘
