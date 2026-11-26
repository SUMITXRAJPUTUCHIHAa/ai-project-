-- PostgreSQL schema (SQLAlchemy create_all produces the same structure; use this for manual migrations)
CREATE TABLE IF NOT EXISTS conversation_logs (
    id            SERIAL PRIMARY KEY,
    session_id    VARCHAR(64) NOT NULL,
    user_query    TEXT NOT NULL,
    detected_intent VARCHAR(64),
    slots         TEXT DEFAULT '{}',
    rule_id       VARCHAR(64),
    is_answered   BOOLEAN DEFAULT TRUE,
    confidence    DOUBLE PRECISION DEFAULT 0,
    version       VARCHAR(16) DEFAULT '2.4',
    is_seed       BOOLEAN DEFAULT FALSE,
    timestamp     TIMESTAMP DEFAULT (now() at time zone 'utc')
);
CREATE INDEX IF NOT EXISTS ix_logs_session ON conversation_logs(session_id);
CREATE INDEX IF NOT EXISTS ix_logs_intent ON conversation_logs(detected_intent);
CREATE INDEX IF NOT EXISTS ix_logs_rule ON conversation_logs(rule_id);
CREATE INDEX IF NOT EXISTS ix_logs_answered ON conversation_logs(is_answered);
CREATE INDEX IF NOT EXISTS ix_logs_version ON conversation_logs(version);
CREATE INDEX IF NOT EXISTS ix_logs_seed ON conversation_logs(is_seed);
CREATE INDEX IF NOT EXISTS ix_logs_ts ON conversation_logs(timestamp);

CREATE TABLE IF NOT EXISTS custom_rules (
    id         SERIAL PRIMARY KEY,
    rule_id    VARCHAR(64) UNIQUE NOT NULL,
    label      VARCHAR(80),
    pattern    TEXT NOT NULL,
    response   TEXT NOT NULL,
    active     BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT (now() at time zone 'utc')
);

CREATE TABLE IF NOT EXISTS session_state (
    session_id VARCHAR(64) PRIMARY KEY,
    state_json TEXT NOT NULL DEFAULT '{}',
    updated_at TIMESTAMP DEFAULT (now() at time zone 'utc')
);

CREATE TABLE IF NOT EXISTS escalations (
    id         SERIAL PRIMARY KEY,
    session_id VARCHAR(64),
    user_query TEXT,
    contact    VARCHAR(160),
    created_at TIMESTAMP DEFAULT (now() at time zone 'utc')
);
