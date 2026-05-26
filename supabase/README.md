# Supabase — CEFIS AI Tutor

Este diretório contém as migrações SQL para o banco de dados Supabase Cloud do projeto.

---

## Pré-requisitos

- Projeto criado no [Supabase Cloud](https://supabase.com) (tier gratuito é suficiente)
- Variáveis de ambiente configuradas no `.env`:
  ```
  SUPABASE_URL=https://<seu-projeto>.supabase.co
  SUPABASE_SERVICE_KEY=<sua-service-role-key>
  ```

---

## 1. Como executar a migração no Supabase SQL Editor

1. Acesse o [Supabase Dashboard](https://supabase.com/dashboard) e abra seu projeto.
2. No menu lateral, clique em **SQL Editor**.
3. Clique em **New query**.
4. Copie e cole o conteúdo completo do arquivo `migrations/001_initial_schema.sql`.
5. Clique em **Run** (ou pressione `Ctrl+Enter`).
6. Verifique que não houve erros no painel de resultados.

Para confirmar que tudo foi criado corretamente, execute:

```sql
-- Verificar tabelas
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('transcript_chunks', 'generated_content_chunks');

-- Verificar seed data (deve retornar 50 linhas)
SELECT COUNT(*) FROM transcript_chunks;

-- Verificar funções RPC
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name IN (
    'match_generated_chunks',
    'match_chunks_by_course',
    'match_chunks_global'
  );
```

---

## 2. Sobre os embeddings do seed data

Os 50 chunks inseridos pela migração usam **embeddings placeholder** — vetores de 768 zeros (`array_fill(0, ARRAY[768])::vector`).

**Isso significa que:**
- O RAG de similaridade **não funcionará corretamente** com esses chunks até que o indexer seja executado.
- Consultas de similaridade retornarão score `0.0` para todos os chunks seed, ficando abaixo do threshold padrão de `0.70`.
- O sistema fará fallback para geração com Gemini puro (sem contexto RAG) até que os embeddings reais sejam gerados.

Os chunks seed existem apenas como **dados de fallback estrutural** — garantem que as tabelas não estejam vazias e que as queries SQL funcionem sem erros.

---

## 3. Como executar o indexer para gerar embeddings reais

O indexer lê as transcrições das aulas da CEFIS, gera embeddings via Gemini `text-embedding-004` e insere (ou atualiza) os chunks no Supabase.

### Pré-requisitos

- Arquivo `transcripts.zip` (ou `transcripts.json`) com as transcrições das aulas CEFIS colocado em `./data/`
- Variáveis de ambiente configuradas (`.env`):
  ```
  GEMINI_API_KEY=...
  SUPABASE_URL=...
  SUPABASE_SERVICE_KEY=...
  TRANSCRIPTS_PATH=/data/transcripts.zip
  ```

### Executar via Docker Compose (recomendado)

```bash
# Dev
docker compose -f docker-compose.dev.yml run --rm indexer

# Prod
docker compose -f docker-compose.prod.yml run --rm indexer
```

### Executar diretamente (sem Docker)

```bash
cd backend/indexer
pip install -r requirements.txt
python indexer.py
```

O indexer é idempotente: se a tabela `transcript_chunks` já contiver dados, ele encerra sem reindexar. Para forçar reindexação, limpe a tabela primeiro:

```sql
TRUNCATE TABLE transcript_chunks;
```

---

## Estrutura dos arquivos

```
supabase/
├── migrations/
│   └── 001_initial_schema.sql   # Schema completo + seed data
└── README.md                    # Este arquivo
```

---

## Resumo das tabelas e funções criadas

| Objeto | Tipo | Descrição |
|---|---|---|
| `transcript_chunks` | Tabela | Chunks de transcrições CEFIS com embeddings |
| `generated_content_chunks` | Tabela | Chunks de conteúdo gerado em tempo real |
| `match_generated_chunks` | RPC | RAG no conteúdo gerado (filtro por session_id) |
| `match_chunks_by_course` | RPC | RAG nas transcrições (filtro por course_id) |
| `match_chunks_global` | RPC | RAG nas transcrições (sem filtro de curso) |
