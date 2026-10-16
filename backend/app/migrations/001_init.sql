CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    filename text NOT NULL,
    content_type text NOT NULL,
    sha256 text NOT NULL UNIQUE,
    size_bytes integer NOT NULL,
    page_count integer,
    chunk_count integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
    error text,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Original files live apart from the metadata, so listing documents never reads the bytes.
CREATE TABLE document_files (
    document_id uuid PRIMARY KEY REFERENCES documents (id) ON DELETE CASCADE,
    data bytea NOT NULL
);

CREATE TABLE chunks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    ordinal integer NOT NULL,
    page integer,
    content text NOT NULL,
    embedding vector(384) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    UNIQUE (document_id, ordinal)
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);

CREATE TABLE conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title text NOT NULL,
    document_ids uuid[],
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX conversations_updated_idx ON conversations (updated_at DESC);

CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    -- Assistant answers: text segments with their citations, and the passages that were retrieved.
    segments jsonb,
    sources jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX messages_conversation_idx ON messages (conversation_id, created_at);
