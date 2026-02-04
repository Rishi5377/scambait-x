-- ScamBait-X PostgreSQL Schema
-- Intelligence Database for threat tracking

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    persona_id VARCHAR(50) NOT NULL,
    current_mode VARCHAR(20) DEFAULT 'patience',
    turn_count INTEGER DEFAULT 0,
    urgency_signals INTEGER DEFAULT 0,
    greed_signals INTEGER DEFAULT 0,
    scam_type VARCHAR(50),
    scam_confidence FLOAT,
    threat_level VARCHAR(20),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Messages table
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'scammer' or 'honeypot'
    content TEXT NOT NULL,
    raw_content TEXT,  -- Before humanization
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Extracted entities (IOCs)
CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    entity_type VARCHAR(30) NOT NULL,  -- 'upi', 'phone', 'bank', 'crypto', 'url', 'email'
    value TEXT NOT NULL,
    normalized_value TEXT,  -- For deduplication
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(session_id, entity_type, normalized_value)
);

-- Intelligence reports
CREATE TABLE IF NOT EXISTS intelligence_reports (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES sessions(id),
    report_data JSONB NOT NULL,
    threat_level VARCHAR(20),
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scammer profiles (aggregated from multiple sessions)
CREATE TABLE IF NOT EXISTS scammer_profiles (
    id SERIAL PRIMARY KEY,
    fingerprint VARCHAR(64) UNIQUE,  -- Hash of identifying characteristics
    known_upi_ids TEXT[],
    known_phones TEXT[],
    known_bank_accounts TEXT[],
    scam_types TEXT[],
    total_sessions INTEGER DEFAULT 1,
    avg_confidence FLOAT,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Threat graph edges (for NetworkX)
CREATE TABLE IF NOT EXISTS threat_edges (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(30) NOT NULL,
    source_value TEXT NOT NULL,
    target_type VARCHAR(30) NOT NULL,
    target_value TEXT NOT NULL,
    relationship VARCHAR(50) NOT NULL,  -- 'linked_to', 'used_by', 'same_campaign'
    weight FLOAT DEFAULT 1.0,
    session_id UUID REFERENCES sessions(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ML embeddings cache
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    text_hash VARCHAR(64) UNIQUE,
    embedding FLOAT[] NOT NULL,
    model_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sessions_persona ON sessions(persona_id);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_entities_session ON entities(session_id);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_threat_edges_source ON threat_edges(source_type, source_value);
CREATE INDEX IF NOT EXISTS idx_threat_edges_target ON threat_edges(target_type, target_value);
