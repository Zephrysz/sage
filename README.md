# CEFIS AI Tutor

Tutor de estudos personalizado com IA, construído sobre o catálogo real da CEFIS. O aluno conversa com o tutor, recebe um diagnóstico de conhecimento, e obtém um plano de estudos adaptado ao seu objetivo, nível e tempo disponível — com conteúdo gerado sob demanda em múltiplos formatos.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Fluxo Principal](#fluxo-principal)
- [Funcionalidades](#funcionalidades)
- [Arquitetura](#arquitetura)
- [Stack Tecnológica](#stack-tecnológica)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Configuração e Execução](#configuração-e-execução)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [API Reference](#api-reference)
- [Indexador de Transcrições](#indexador-de-transcrições)

---

## Visão Geral

O CEFIS AI Tutor resolve um problema real: o aluno sabe que quer crescer profissionalmente, mas não sabe por onde começar nem como aproveitar o catálogo da CEFIS de forma eficiente.

A solução combina três camadas de inteligência:

1. **Onboarding conversacional** — o tutor coleta perfil, objetivo e estilo de aprendizado via chat natural, sem formulários.
2. **Diagnóstico adaptativo** — questões de múltipla escolha geradas pelo Gemini, calibradas ao nível e área do aluno, identificam lacunas de conhecimento.
3. **Plano personalizado** — o Gemini filtra o catálogo real da CEFIS por relevância semântica (via RAG sobre transcrições indexadas) e monta um plano com cursos reais + conteúdo gerado para cobrir lacunas não atendidas pelo catálogo.

---

## Fluxo Principal

```
Login CEFIS
    │
    ▼
Onboarding (chat)
  ├─ Área de interesse
  ├─ Objetivo profissional
  ├─ Nível de experiência
  ├─ Tempo disponível por sessão
  └─ Estilo de aprendizado
    │
    ▼
Diagnóstico (MCQ)
  ├─ 5 questões geradas pelo Gemini
  ├─ Calibradas ao nível + área
  └─ Resultado: nível, score, lacunas identificadas
    │
    ▼
Plano de Estudos
  ├─ Gemini filtra catálogo CEFIS por relevância
  ├─ RAG sobre transcrições reforça a filtragem
  ├─ Cursos CEFIS relevantes → itens do plano
  ├─ Lacunas sem cobertura → conteúdo gerado pela IA
  └─ Justificativa personalizada para cada item
    │
    ▼
Modo Estudo (por item do plano)
  ├─ Cursos CEFIS: player de vídeo + lista de aulas + chatbot contextual
  └─ Conteúdo gerado: Resumo | Apostila | Mini-Podcast (com TTS)
```

---

## Funcionalidades

### Onboarding Inteligente
- Chat em linguagem natural — sem formulários
- Extração estruturada de perfil via Gemini (JSON schema)
- Confirmação antes de avançar para o diagnóstico

### Diagnóstico de Conhecimento
- Questões MCQ (5 alternativas) geradas dinamicamente pelo Gemini
- Calibradas ao nível declarado e à área de interesse
- Identifica lacunas críticas e secundárias por tópico

### Plano de Estudos Personalizado
- Filtragem semântica do catálogo CEFIS via Gemini + RAG
- Quando o catálogo não tem cursos relevantes, o plano é preenchido com conteúdo gerado — sem fallback silencioso
- Limite de itens adaptado ao tempo disponível (2–8 itens)
- Priorização de lacunas críticas
- Justificativa gerada por IA para cada item
- Destaque de aulas mais relevantes em cursos longos
- Indicador de certificado já obtido

### Modo Estudo — Cursos CEFIS
- Player de vídeo integrado com fontes HD/SD da CEFIS
- Sidebar colapsável com lista de aulas e duração
- Chatbot contextual ao lado do vídeo — responde dúvidas sobre o conteúdo da aula atual

### Modo Estudo — Conteúdo Gerado
- **Resumo**: texto de 250–350 palavras baseado nas transcrições indexadas (RAG)
- **Apostila**: material estruturado em markdown com Introdução, Conceitos Principais, Exemplos Práticos e Pontos de Atenção
- **Mini-Podcast**: roteiro narrado (~3 min), com síntese de voz via Gemini TTS (9 vozes disponíveis, velocidade ajustável, download em WAV)
- Streaming em tempo real (SSE) para todos os formatos
- Chatbot disponível ao lado do conteúdo gerado

### Integração CEFIS
- Login com credenciais CEFIS (email + senha)
- Catálogo de cursos via API v3
- Detalhes e aulas por curso
- Certificados do aluno (marcados no plano)
- Fontes de stream seguras (link_secure, preferência HD)

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                  │
│  /login  →  /tutor  →  /tutor/study/:id                 │
│                     →  /tutor/content/:id               │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────┐
│                    Backend (FastAPI)                      │
│                                                          │
│  /session   /chat   /diagnosis   /plan   /content        │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ GeminiService│  │  RagService  │  │ CefisService  │  │
│  │ (chat, MCQ,  │  │ (pgvector    │  │ (API v1 + v3) │  │
│  │  embed, TTS) │  │  Supabase)   │  │               │  │
│  └──────────────┘  └──────┬───────┘  └───────────────┘  │
│                           │                              │
└───────────────────────────┼──────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────┐
│                    Supabase (pgvector)                    │
│  Tabela: transcript_chunks                               │
│  Funções RPC: match_chunks_global, match_chunks_by_course│
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    Indexer (standalone)                   │
│  Lê transcrições JSON → gera embeddings → insere no      │
│  Supabase via pgvector                                   │
└──────────────────────────────────────────────────────────┘
```

### Sessão e Estado
O backend mantém sessões em arquivo JSON (`sessions.json`). Cada sessão percorre os estados:

```
ONBOARDING → AWAITING_CONFIRMATION → DIAGNOSIS → PLAN_READY → STUDY_MODE
```

### RAG (Retrieval-Augmented Generation)
As transcrições dos cursos CEFIS são indexadas como chunks com embeddings de 768 dimensões (`gemini-embedding-001`). Na hora de montar o plano, o sistema consulta o índice com o objetivo + área + lacunas do aluno para identificar quais cursos do catálogo têm conteúdo diretamente relevante.

---

## Stack Tecnológica

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS |
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| IA | Google Gemini 2.5 Flash (chat, MCQ, filtragem, TTS) |
| Embeddings | Gemini Embedding 001 (768 dims) |
| Banco vetorial | Supabase + pgvector |
| API CEFIS | v1 (auth) + v3 (cursos, aulas, certificados) |
| Infra | Docker Compose, uv (Python package manager) |

---

## Estrutura do Projeto

```
hackathonAI/
├── backend/
│   ├── main.py                  # FastAPI app, routers, CORS
│   ├── config.py                # Configurações via env vars
│   ├── session_store.py         # Persistência de sessões em JSON
│   ├── models/
│   │   ├── session.py           # Session, Profile, estados
│   │   ├── diagnosis.py         # DiagnosisResult, Gap, MCQ
│   │   ├── plan.py              # StudyPlan, PlanItem, PlanItemType
│   │   └── content.py           # ContentSource
│   ├── routers/
│   │   ├── session.py           # Login, estado, perfil
│   │   ├── chat.py              # Chat SSE, onboarding
│   │   ├── diagnosis.py         # Start, submit MCQ
│   │   ├── plan.py              # GET /plan, POST /plan/adjust
│   │   └── content.py           # Resumo, apostila, podcast, TTS
│   ├── services/
│   │   ├── gemini_service.py    # Chat, MCQ, embed, TTS
│   │   ├── cefis_service.py     # API v1 + v3 wrapper
│   │   ├── rag_service.py       # Query pgvector via Supabase RPC
│   │   ├── plan_service.py      # build_plan, adjust_plan
│   │   └── content_service.py   # Resumo, apostila, podcast
│   └── indexer/
│       ├── indexer.py           # Indexa transcrições → Supabase
│       └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── login/           # Tela de login CEFIS
│       │   └── tutor/
│       │       ├── page.tsx         # Chat + diagnóstico + plano
│       │       ├── study/[courseId] # Player + sidebar + chatbot
│       │       └── content/[itemId] # Resumo / apostila / podcast
│       ├── components/
│       │   ├── plan/            # StudyPlanList, PlanItemCard
│       │   ├── diagnosis/       # DiagnosisQuestion, DiagnosisResult
│       │   └── study/           # LessonSidebar, VideoPlayer, StudyChatbot
│       └── hooks/
│           └── useSession.ts    # Estado global da sessão
├── data/
│   └── Transcricoes/            # Transcrições dos cursos CEFIS
├── docker-compose.prod.yml
├── docker-compose.dev.yml
└── Makefile
```

---

## Configuração e Execução

### Pré-requisitos
- Docker e Docker Compose
- Conta Google AI Studio (Gemini API Key)
- Projeto Supabase com extensão pgvector habilitada
- Credenciais CEFIS válidas para teste

### 1. Clonar e configurar variáveis de ambiente

```bash
cp backend/.env.example backend/.env
# Edite backend/.env com suas chaves
```

### 2. Configurar o Supabase

Execute as migrations para criar a tabela `transcript_chunks` e as funções RPC:

```bash
make migrate-run
```

### 3. Indexar as transcrições

```bash
docker compose -f docker-compose.prod.yml run --rm indexer
```

### 4. Subir o ambiente de desenvolvimento

```bash
make up
```

Ou produção:

```bash
make up-prod
```

### Comandos úteis

```bash
make logs        # Acompanhar logs em tempo real
make down        # Parar containers
make build       # Rebuild sem cache
make ps          # Status dos containers
```

### Endpoints disponíveis

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Docs (Swagger) | http://localhost:8000/docs |

---

## Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| `GEMINI_API_KEY` | Chave da API Google Gemini (AI Studio) |
| `SUPABASE_URL` | URL do projeto Supabase |
| `SUPABASE_SERVICE_KEY` | Service role key do Supabase |
| `PGHOST` / `PGPORT` / `PGDATABASE` / `PGUSER` / `PGPASSWORD` | Conexão direta ao Postgres (indexer) |
| `TRANSCRIPTS_PATH` | Caminho para as transcrições dos cursos |
| `CORS_ORIGINS` | Origins permitidas (separadas por vírgula) |
| `SESSION_STORE_PATH` | Caminho do arquivo de sessões JSON |
| `PORT` | Porta do backend (padrão: 8000) |
| `NEXT_PUBLIC_API_URL` | URL do backend (baked no bundle Next.js) |

---

## API Reference

### Session
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/session/login` | Login com credenciais CEFIS |
| `GET` | `/session/me` | Dados da sessão atual |
| `POST` | `/session/state` | Atualiza estado da sessão |

### Chat
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/chat/message` | Envia mensagem (SSE streaming) |

### Diagnosis
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/diagnosis/start` | Gera questões MCQ |
| `POST` | `/diagnosis/submit` | Submete respostas e obtém resultado |

### Plan
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/plan` | Gera e retorna o plano de estudos |
| `POST` | `/plan/adjust` | Recalcula o plano com novo tempo disponível |

### Content
| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/content/generate` | Gera resumo ou apostila (SSE) |
| `POST` | `/content/podcast/script` | Gera roteiro de podcast (SSE) |
| `POST` | `/content/podcast/synthesize` | Sintetiza áudio WAV via Gemini TTS |
| `GET` | `/content/tts/voices` | Lista vozes TTS disponíveis |

---

## Indexador de Transcrições

O indexer lê a estrutura de diretórios em `data/Transcricoes/courses/output/`, extrai o texto das transcrições de cada aula, divide em chunks, gera embeddings via `gemini-embedding-001` e insere no Supabase.

Estrutura esperada:
```
output/
└── {course_id}/
    ├── details.json
    └── lessons/
        └── {lesson_id}/
            └── transcript.json (ou similar)
```

O índice alimenta o RAG que é usado tanto na filtragem de cursos do plano quanto na geração de conteúdo contextualizado (resumos e apostilas baseados no conteúdo real das aulas).
