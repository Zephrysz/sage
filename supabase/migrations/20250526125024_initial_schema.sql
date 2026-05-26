-- =============================================================================
-- CEFIS AI Tutor — Initial Schema Migration
-- Run this file in the Supabase SQL Editor (once, on a fresh project)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Enable pgvector extension
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS vector;


-- ---------------------------------------------------------------------------
-- 2. transcript_chunks
--    Populated by the one-shot indexer (indexer.py) from CEFIS transcripts.
--    Used for: semantic course ranking in the study plan.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcript_chunks (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   TEXT        NOT NULL,
  lesson_id   TEXT        NOT NULL,
  course_name TEXT        NOT NULL,
  lesson_name TEXT        NOT NULL,
  content     TEXT        NOT NULL,
  embedding   vector(768),
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ivfflat index — cosine distance
CREATE INDEX IF NOT EXISTS transcript_chunks_embedding_idx
  ON transcript_chunks
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);


-- ---------------------------------------------------------------------------
-- 3. generated_content_chunks
--    Populated in real-time after each content generation (summary/apostila).
--    Used for: contextual chatbot RAG (primary source).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS generated_content_chunks (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    TEXT        NOT NULL,
  plan_item_id  TEXT        NOT NULL,
  content_type  TEXT        NOT NULL,   -- 'SUMMARY' | 'APOSTILA' | 'PODCAST'
  content       TEXT        NOT NULL,
  embedding     vector(768),
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- ivfflat index — cosine distance, 50 lists (smaller table, fewer lists needed)
CREATE INDEX IF NOT EXISTS generated_content_chunks_embedding_idx
  ON generated_content_chunks
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);


-- ---------------------------------------------------------------------------
-- 4. RPC: match_generated_chunks
--    Primary RAG source for the study-mode chatbot.
--    Filters by session_id so each student only sees their own content.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_generated_chunks(
  query_embedding   vector(768),
  session_id_filter text,
  match_threshold   float,
  match_count       int
)
RETURNS TABLE (content text, similarity float)
LANGUAGE sql STABLE AS $$
  SELECT content, 1 - (embedding <=> query_embedding) AS similarity
  FROM generated_content_chunks
  WHERE session_id = session_id_filter
    AND 1 - (embedding <=> query_embedding) >= match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


-- ---------------------------------------------------------------------------
-- 5. RPC: match_chunks_by_course
--    Fallback RAG + course ranking — filters by course_id.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_chunks_by_course(
  query_embedding   vector(768),
  course_id_filter  text,
  match_threshold   float,
  match_count       int
)
RETURNS TABLE (
  id          uuid,
  course_id   text,
  lesson_id   text,
  course_name text,
  lesson_name text,
  content     text,
  similarity  float
)
LANGUAGE sql STABLE AS $$
  SELECT id, course_id, lesson_id, course_name, lesson_name, content,
         1 - (embedding <=> query_embedding) AS similarity
  FROM transcript_chunks
  WHERE course_id = course_id_filter
    AND 1 - (embedding <=> query_embedding) >= match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


-- ---------------------------------------------------------------------------
-- 6. RPC: match_chunks_global
--    Global fallback — no course filter, searches all transcript_chunks.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_chunks_global(
  query_embedding vector(768),
  match_threshold float,
  match_count     int
)
RETURNS TABLE (
  id          uuid,
  course_id   text,
  lesson_id   text,
  course_name text,
  lesson_name text,
  content     text,
  similarity  float
)
LANGUAGE sql STABLE AS $$
  SELECT id, course_id, lesson_id, course_name, lesson_name, content,
         1 - (embedding <=> query_embedding) AS similarity
  FROM transcript_chunks
  WHERE 1 - (embedding <=> query_embedding) >= match_threshold
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;


-- =============================================================================
-- 7. Seed data — ~50 representative chunks (fallback while indexer hasn't run)
--
-- IMPORTANT: embeddings are placeholder zeros (array_fill(0, ARRAY[768])::vector).
-- Real embeddings MUST be generated by running the indexer (indexer.py), which
-- calls the Gemini text-embedding-004 API and overwrites these rows.
-- Until the indexer runs, RAG similarity scores will be 0 for all seed chunks
-- and the system will fall back to Gemini-only generation.
-- =============================================================================

INSERT INTO transcript_chunks (course_id, lesson_id, course_name, lesson_name, content, embedding) VALUES

-- -------------------------------------------------------------------------
-- Curso seed-001: Mercado de Capitais (10 chunks)
-- -------------------------------------------------------------------------
(
  'seed-001', 'seed-001-aula-01',
  'Mercado de Capitais', 'Introdução ao Mercado de Capitais',
  'O mercado de capitais é um sistema de distribuição de valores mobiliários que proporciona liquidez aos títulos emitidos pelas empresas e viabiliza o processo de capitalização. Ele conecta agentes superavitários, que possuem recursos disponíveis para investir, com agentes deficitários, que necessitam de capital para financiar suas atividades produtivas.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-01',
  'Mercado de Capitais', 'Introdução ao Mercado de Capitais',
  'A Comissão de Valores Mobiliários (CVM) é o órgão regulador do mercado de capitais brasileiro, responsável por fiscalizar, normatizar e desenvolver o mercado de valores mobiliários. A CVM atua para proteger os investidores e garantir o funcionamento eficiente e transparente do mercado.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-02',
  'Mercado de Capitais', 'Ações: Conceitos e Tipos',
  'As ações são títulos de propriedade que representam uma fração do capital social de uma empresa. Ao adquirir ações, o investidor torna-se sócio da companhia e passa a ter direito a participar dos resultados, seja por meio de dividendos ou pela valorização do papel na bolsa de valores.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-02',
  'Mercado de Capitais', 'Ações: Conceitos e Tipos',
  'As ações ordinárias (ON) conferem ao acionista o direito a voto nas assembleias da empresa, enquanto as ações preferenciais (PN) geralmente não concedem direito a voto, mas garantem prioridade no recebimento de dividendos e no reembolso do capital em caso de liquidação da companhia.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-03',
  'Mercado de Capitais', 'Mercado Primário e Secundário',
  'O mercado primário é onde ocorre a emissão de novos títulos pelas empresas, com o objetivo de captar recursos diretamente dos investidores. As ofertas públicas iniciais (IPO) e as ofertas subsequentes (follow-on) são exemplos de operações realizadas no mercado primário.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-03',
  'Mercado de Capitais', 'Mercado Primário e Secundário',
  'O mercado secundário é onde os títulos já emitidos são negociados entre investidores, sem que os recursos cheguem à empresa emissora. A bolsa de valores (B3 no Brasil) é o principal ambiente do mercado secundário, proporcionando liquidez e formação de preços para os ativos.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-04',
  'Mercado de Capitais', 'Índices de Mercado',
  'O Ibovespa é o principal índice de desempenho das ações negociadas na B3, representando a carteira teórica dos ativos de maior negociabilidade e representatividade do mercado acionário brasileiro. Ele é revisado periodicamente para refletir as mudanças no perfil de negociação do mercado.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-04',
  'Mercado de Capitais', 'Índices de Mercado',
  'Além do Ibovespa, existem outros índices relevantes como o IFIX (fundos imobiliários), o IDIV (empresas pagadoras de dividendos) e o SMLL (small caps). Cada índice tem critérios específicos de composição e serve como referência para diferentes estratégias de investimento.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-05',
  'Mercado de Capitais', 'Derivativos e Mercado Futuro',
  'Os derivativos são instrumentos financeiros cujo valor deriva de um ativo subjacente, como ações, moedas, commodities ou índices. Os principais tipos de derivativos são: contratos futuros, opções, swaps e contratos a termo, cada um com características e finalidades distintas.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-001', 'seed-001-aula-05',
  'Mercado de Capitais', 'Derivativos e Mercado Futuro',
  'O mercado futuro permite que investidores e empresas se protejam contra oscilações de preços (hedge) ou especulem sobre a direção futura dos ativos. No Brasil, a B3 é a principal câmara de compensação e liquidação de contratos futuros, garantindo a integridade das operações.',
  array_fill(0, ARRAY[768])::vector
),

-- -------------------------------------------------------------------------
-- Curso seed-002: Renda Fixa (10 chunks)
-- -------------------------------------------------------------------------
(
  'seed-002', 'seed-002-aula-01',
  'Renda Fixa', 'Conceitos Fundamentais de Renda Fixa',
  'Renda fixa é uma categoria de investimento em que as condições de remuneração são definidas no momento da aplicação, podendo ser prefixadas, pós-fixadas ou híbridas. O investidor empresta dinheiro ao emissor (governo, banco ou empresa) e recebe de volta o principal acrescido de juros ao final do prazo.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-01',
  'Renda Fixa', 'Conceitos Fundamentais de Renda Fixa',
  'Os títulos prefixados têm taxa de juros definida no momento da compra, como o Tesouro Prefixado. Os pós-fixados acompanham um indexador, como a Selic ou o CDI. Os híbridos combinam uma taxa fixa com um indexador de inflação, como o Tesouro IPCA+, protegendo o poder de compra do investidor.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-02',
  'Renda Fixa', 'Tesouro Direto',
  'O Tesouro Direto é um programa do governo federal que permite a pessoas físicas investir em títulos públicos federais pela internet. É considerado o investimento mais seguro do Brasil, pois é garantido pelo Tesouro Nacional, e oferece títulos com diferentes prazos e indexadores para atender a distintos perfis de investidor.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-02',
  'Renda Fixa', 'Tesouro Direto',
  'Os principais títulos do Tesouro Direto são: Tesouro Selic (pós-fixado, ideal para reserva de emergência), Tesouro Prefixado (taxa fixa, bom para cenários de queda de juros) e Tesouro IPCA+ (híbrido, protege contra a inflação e é indicado para objetivos de longo prazo como aposentadoria).',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-03',
  'Renda Fixa', 'CDB, LCI e LCA',
  'O CDB (Certificado de Depósito Bancário) é um título emitido por bancos para captar recursos. O investidor empresta dinheiro ao banco e recebe juros em troca. Os CDBs são garantidos pelo FGC (Fundo Garantidor de Créditos) até R$ 250 mil por CPF por instituição, o que os torna investimentos de baixo risco.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-03',
  'Renda Fixa', 'CDB, LCI e LCA',
  'LCI (Letra de Crédito Imobiliário) e LCA (Letra de Crédito do Agronegócio) são títulos isentos de Imposto de Renda para pessoas físicas, o que os torna atrativos mesmo com taxas nominais menores que CDBs. Ambos são garantidos pelo FGC e financiam, respectivamente, o setor imobiliário e o agronegócio.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-04',
  'Renda Fixa', 'Debêntures e CRI/CRA',
  'Debêntures são títulos de dívida emitidos por empresas para captar recursos no mercado. Diferentemente dos CDBs, não contam com garantia do FGC, portanto o risco de crédito é maior. As debêntures incentivadas (Lei 12.431) são isentas de IR para pessoas físicas e financiam projetos de infraestrutura.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-04',
  'Renda Fixa', 'Debêntures e CRI/CRA',
  'CRI (Certificado de Recebíveis Imobiliários) e CRA (Certificado de Recebíveis do Agronegócio) são títulos de securitização isentos de IR para pessoas físicas. Eles representam promessas de pagamento lastreadas em créditos imobiliários ou do agronegócio e são emitidos por securitizadoras, não por bancos.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-05',
  'Renda Fixa', 'Marcação a Mercado e Duration',
  'A marcação a mercado é o processo de atualizar o valor dos títulos de renda fixa diariamente com base nas taxas de juros vigentes no mercado. Quando as taxas sobem, o preço dos títulos prefixados cai; quando as taxas caem, o preço sobe. Isso afeta o investidor que precisa vender o título antes do vencimento.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-002', 'seed-002-aula-05',
  'Renda Fixa', 'Marcação a Mercado e Duration',
  'Duration é uma medida de sensibilidade do preço de um título às variações nas taxas de juros. Quanto maior a duration, maior a volatilidade do preço do título frente a mudanças nas taxas. Títulos de longo prazo têm duration maior e, portanto, são mais sensíveis às oscilações da política monetária.',
  array_fill(0, ARRAY[768])::vector
),

-- -------------------------------------------------------------------------
-- Curso seed-003: Análise Fundamentalista (10 chunks)
-- -------------------------------------------------------------------------
(
  'seed-003', 'seed-003-aula-01',
  'Análise Fundamentalista', 'Introdução à Análise Fundamentalista',
  'A análise fundamentalista é uma metodologia de avaliação de empresas que busca determinar o valor intrínseco de uma ação com base em dados econômicos, financeiros e qualitativos. O objetivo é identificar se uma ação está sendo negociada abaixo (subavaliada) ou acima (sobreavaliada) do seu valor real.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-01',
  'Análise Fundamentalista', 'Introdução à Análise Fundamentalista',
  'Os fundamentos analisados incluem demonstrações financeiras (balanço patrimonial, DRE e fluxo de caixa), indicadores de mercado (P/L, P/VP, EV/EBITDA), qualidade da gestão, vantagens competitivas (moat) e perspectivas do setor. A análise fundamentalista é a base do investimento em valor (value investing).',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-02',
  'Análise Fundamentalista', 'Demonstrações Financeiras',
  'O balanço patrimonial apresenta a situação financeira da empresa em um determinado momento, mostrando seus ativos (bens e direitos), passivos (obrigações) e patrimônio líquido. A equação fundamental é: Ativo = Passivo + Patrimônio Líquido. Analisar a evolução do balanço ao longo do tempo revela tendências importantes.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-02',
  'Análise Fundamentalista', 'Demonstrações Financeiras',
  'A Demonstração do Resultado do Exercício (DRE) mostra a performance da empresa em um período, partindo da receita bruta e chegando ao lucro líquido após deduzir custos, despesas, depreciação, juros e impostos. O EBITDA (lucro antes de juros, impostos, depreciação e amortização) é amplamente usado para comparar a eficiência operacional entre empresas.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-03',
  'Análise Fundamentalista', 'Múltiplos de Valuation',
  'O índice P/L (Preço/Lucro) indica quantos anos de lucro atual seriam necessários para recuperar o investimento na ação. Um P/L baixo pode indicar que a ação está barata, mas também pode refletir perspectivas ruins de crescimento. É fundamental comparar o P/L com empresas do mesmo setor e com a média histórica da própria empresa.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-03',
  'Análise Fundamentalista', 'Múltiplos de Valuation',
  'O EV/EBITDA (Enterprise Value sobre EBITDA) é um múltiplo que compara o valor total da empresa (incluindo dívida) com sua geração de caixa operacional. É especialmente útil para comparar empresas com diferentes estruturas de capital. Um EV/EBITDA baixo em relação ao setor pode indicar uma oportunidade de investimento.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-04',
  'Análise Fundamentalista', 'Dividendos e Dividend Yield',
  'Dividendos são a parcela do lucro distribuída pela empresa aos seus acionistas. O Dividend Yield (DY) é calculado dividindo o dividendo por ação pelo preço atual da ação, expressando o retorno em dividendos como percentual do investimento. Empresas com DY consistentemente alto são chamadas de "pagadoras de dividendos".',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-04',
  'Análise Fundamentalista', 'Dividendos e Dividend Yield',
  'O payout ratio indica qual percentual do lucro líquido é distribuído como dividendos. Um payout muito alto pode ser insustentável se a empresa não gerar caixa suficiente, enquanto um payout baixo pode indicar que a empresa está reinvestindo os lucros para crescer. A análise do histórico de dividendos revela a consistência da política de distribuição.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-05',
  'Análise Fundamentalista', 'Análise Setorial e Vantagens Competitivas',
  'O modelo das Cinco Forças de Porter analisa a competitividade de um setor considerando: rivalidade entre concorrentes, ameaça de novos entrantes, poder de barganha dos fornecedores, poder de barganha dos clientes e ameaça de produtos substitutos. Setores com baixa competição tendem a gerar empresas mais lucrativas.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-003', 'seed-003-aula-05',
  'Análise Fundamentalista', 'Análise Setorial e Vantagens Competitivas',
  'O conceito de "moat" (fosso econômico), popularizado por Warren Buffett, refere-se às vantagens competitivas duráveis que protegem uma empresa da concorrência. Exemplos de moat incluem: marcas fortes, efeitos de rede, custos de troca elevados, vantagens de custo e ativos intangíveis como patentes e licenças regulatórias.',
  array_fill(0, ARRAY[768])::vector
),

-- -------------------------------------------------------------------------
-- Curso seed-004: Fundos de Investimento (10 chunks)
-- -------------------------------------------------------------------------
(
  'seed-004', 'seed-004-aula-01',
  'Fundos de Investimento', 'O que são Fundos de Investimento',
  'Um fundo de investimento é uma comunhão de recursos de vários investidores (cotistas) administrada por um gestor profissional. O patrimônio do fundo é dividido em cotas de igual valor, e cada cotista possui um número de cotas proporcional ao valor investido. Os fundos permitem acesso a estratégias e ativos que seriam inviáveis individualmente.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-01',
  'Fundos de Investimento', 'O que são Fundos de Investimento',
  'Os principais participantes de um fundo são: o gestor (toma as decisões de investimento), o administrador (responsabilidades legais e operacionais), o custodiante (guarda os ativos) e o distribuidor (vende as cotas). A CVM regula e fiscaliza os fundos de investimento no Brasil, garantindo transparência e proteção ao cotista.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-02',
  'Fundos de Investimento', 'Tipos de Fundos',
  'Os fundos de renda fixa investem predominantemente em títulos de renda fixa e são indicados para investidores conservadores. Os fundos multimercado têm liberdade para investir em diversas classes de ativos (renda fixa, ações, câmbio, derivativos) e buscam retornos superiores ao CDI com maior flexibilidade de gestão.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-02',
  'Fundos de Investimento', 'Tipos de Fundos',
  'Os fundos de ações investem no mínimo 67% do patrimônio em ações ou ativos relacionados ao mercado acionário. Os fundos cambiais têm pelo menos 80% do patrimônio em ativos relacionados a moedas estrangeiras. Os fundos de índice (ETFs) replicam a carteira de um índice de referência e são negociados na bolsa como ações.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-03',
  'Fundos de Investimento', 'Taxas e Custos',
  'A taxa de administração é cobrada anualmente sobre o patrimônio do fundo e remunera o gestor e o administrador. A taxa de performance é cobrada sobre o rendimento que excede um benchmark (como o CDI ou o Ibovespa) e alinha os interesses do gestor com os do cotista. Ambas as taxas impactam diretamente a rentabilidade líquida.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-03',
  'Fundos de Investimento', 'Taxas e Custos',
  'Além das taxas de administração e performance, alguns fundos cobram taxa de entrada (come-cotas antecipado) e taxa de saída (resgate antecipado). O come-cotas é uma antecipação semestral do Imposto de Renda que reduz o número de cotas do investidor em maio e novembro, afetando o efeito dos juros compostos.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-04',
  'Fundos de Investimento', 'Fundos Imobiliários (FIIs)',
  'Os Fundos de Investimento Imobiliário (FIIs) são fundos que investem em ativos do setor imobiliário, como imóveis físicos (shoppings, galpões logísticos, lajes corporativas) ou títulos imobiliários (CRI, LCI). As cotas são negociadas na B3 e os rendimentos distribuídos mensalmente são isentos de IR para pessoas físicas.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-04',
  'Fundos de Investimento', 'Fundos Imobiliários (FIIs)',
  'Os FIIs são classificados em: FIIs de tijolo (investem em imóveis físicos e geram renda de aluguel), FIIs de papel (investem em títulos de crédito imobiliário como CRI e LCI) e FIIs híbridos (combinam as duas estratégias). O IFIX é o índice de referência dos FIIs negociados na B3.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-05',
  'Fundos de Investimento', 'Como Escolher um Fundo',
  'Para escolher um fundo de investimento, o investidor deve analisar: o histórico de rentabilidade em diferentes cenários de mercado, a consistência dos retornos em relação ao benchmark, as taxas cobradas, a qualidade e experiência da equipe de gestão, a liquidez (prazo de resgate) e a aderência ao seu perfil de risco e objetivos.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-004', 'seed-004-aula-05',
  'Fundos de Investimento', 'Como Escolher um Fundo',
  'O índice Sharpe mede o retorno ajustado ao risco de um fundo, indicando quanto de retorno adicional o fundo gerou por unidade de risco assumido. Um Sharpe maior que 1 é considerado bom. O drawdown máximo indica a maior queda do fundo em relação ao seu pico histórico, sendo uma medida importante de risco para investidores avessos a perdas.',
  array_fill(0, ARRAY[768])::vector
),

-- -------------------------------------------------------------------------
-- Curso seed-005: Planejamento Financeiro (10 chunks)
-- -------------------------------------------------------------------------
(
  'seed-005', 'seed-005-aula-01',
  'Planejamento Financeiro', 'Fundamentos do Planejamento Financeiro',
  'O planejamento financeiro pessoal é o processo de definir objetivos financeiros e criar um plano de ação para alcançá-los. Ele envolve o controle do orçamento, a formação de reservas, a gestão de dívidas e a construção de um patrimônio ao longo do tempo. Um bom planejamento financeiro começa pelo diagnóstico da situação atual.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-01',
  'Planejamento Financeiro', 'Fundamentos do Planejamento Financeiro',
  'A regra 50-30-20 é uma diretriz popular de orçamento: 50% da renda para necessidades básicas (moradia, alimentação, transporte), 30% para desejos e lazer, e 20% para poupança e investimentos. Embora seja uma simplificação, serve como ponto de partida para quem está começando a organizar as finanças.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-02',
  'Planejamento Financeiro', 'Reserva de Emergência',
  'A reserva de emergência é um valor guardado para cobrir despesas inesperadas ou períodos de perda de renda, sem comprometer os investimentos de longo prazo. O valor recomendado é de 3 a 6 meses de despesas mensais para empregados CLT e de 6 a 12 meses para autônomos e empreendedores, dada a maior instabilidade de renda.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-02',
  'Planejamento Financeiro', 'Reserva de Emergência',
  'A reserva de emergência deve ser mantida em investimentos de alta liquidez e baixo risco, como o Tesouro Selic ou CDBs com liquidez diária. O objetivo não é maximizar o rendimento, mas garantir que o dinheiro esteja disponível imediatamente quando necessário, sem risco de perda de capital.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-03',
  'Planejamento Financeiro', 'Gestão de Dívidas',
  'As dívidas podem ser classificadas em "boas" (financiam ativos que se valorizam ou geram renda, como financiamento imobiliário) e "ruins" (financiam consumo com juros altos, como cartão de crédito e cheque especial). A prioridade deve ser sempre quitar as dívidas com as maiores taxas de juros primeiro.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-03',
  'Planejamento Financeiro', 'Gestão de Dívidas',
  'O método "bola de neve" para quitação de dívidas consiste em pagar o mínimo em todas as dívidas e direcionar o máximo possível para a menor dívida primeiro, gerando motivação psicológica com vitórias rápidas. O método "avalanche" prioriza a dívida com maior taxa de juros, sendo matematicamente mais eficiente.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-04',
  'Planejamento Financeiro', 'Previdência e Aposentadoria',
  'A previdência privada complementa a previdência social (INSS) e é uma forma de acumular recursos para a aposentadoria com benefícios fiscais. Os planos PGBL (Plano Gerador de Benefício Livre) permitem deduzir até 12% da renda bruta no IR, sendo indicados para quem faz a declaração completa.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-04',
  'Planejamento Financeiro', 'Previdência e Aposentadoria',
  'O VGBL (Vida Gerador de Benefício Livre) não permite dedução no IR, mas o imposto incide apenas sobre os rendimentos no resgate, sendo indicado para quem faz a declaração simplificada ou já atingiu o limite de dedução do PGBL. A tabela regressiva do IR beneficia quem mantém o plano por mais de 10 anos, com alíquota mínima de 10%.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-05',
  'Planejamento Financeiro', 'Metas Financeiras e Juros Compostos',
  'Os juros compostos são o mecanismo pelo qual os rendimentos de um investimento geram novos rendimentos ao longo do tempo, criando um efeito exponencial de crescimento patrimonial. Albert Einstein teria chamado os juros compostos de "a oitava maravilha do mundo", destacando seu poder de multiplicação de riqueza no longo prazo.',
  array_fill(0, ARRAY[768])::vector
),
(
  'seed-005', 'seed-005-aula-05',
  'Planejamento Financeiro', 'Metas Financeiras e Juros Compostos',
  'Para definir metas financeiras eficazes, utilize o critério SMART: Específicas (o que exatamente você quer?), Mensuráveis (qual o valor?), Atingíveis (é realista dado seu orçamento?), Relevantes (por que é importante?) e Temporais (em quanto tempo?). Metas bem definidas aumentam significativamente a probabilidade de sucesso no planejamento financeiro.',
  array_fill(0, ARRAY[768])::vector
);

-- =============================================================================
-- End of migration
-- =============================================================================
-- Next steps:
--   1. Run the indexer (indexer.py) to replace placeholder embeddings with
--      real Gemini text-embedding-004 vectors from CEFIS transcripts.
--   2. Verify the extension and tables were created:
--        SELECT * FROM transcript_chunks LIMIT 5;
--        SELECT * FROM generated_content_chunks LIMIT 1;
--   3. Test an RPC call (replace the zeros with a real embedding in production):
--        SELECT * FROM match_chunks_global(
--          array_fill(0, ARRAY[768])::vector, 0.0, 5
--        );
-- =============================================================================
