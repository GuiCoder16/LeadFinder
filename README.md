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
                    ┌─────────────────┐
                    │ Exportação CSV  │
                    │      / XLSX     │
                    └─────────────────┘
