-- magicpin AI Challenge — Vera Bot — Supabase schema
-- Run this once in Supabase SQL Editor (project: hmehubbvlqzmdxtacsut)
-- Creates 4 tables: contexts, conversations, suppressions, blocked_merchants
-- Idempotent: re-running is a no-op (CREATE TABLE IF NOT EXISTS)

-- ─── 1) contexts ─────────────────────────────────────────────────────────────
-- Stores all 4 context types pushed via POST /v1/context.
-- Primary key (scope, context_id) — version semantics: higher version replaces lower.
CREATE TABLE IF NOT EXISTS contexts (
    scope         TEXT        NOT NULL,
    context_id    TEXT        NOT NULL,
    version       INTEGER     NOT NULL,
    payload       JSONB       NOT NULL,
    delivered_at  TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope, context_id)
);

CREATE INDEX IF NOT EXISTS contexts_scope_idx ON contexts (scope);
CREATE INDEX IF NOT EXISTS contexts_updated_idx ON contexts (updated_at DESC);

COMMENT ON TABLE contexts IS 'Versioned context store: 4 scopes (category, merchant, customer, trigger). Higher version replaces lower atomically.';

-- ─── 2) conversations ────────────────────────────────────────────────────────
-- Stores multi-turn conversation state for /v1/reply continuity.
-- turns is an append-only JSONB array of turn objects.
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id   TEXT        PRIMARY KEY,
    merchant_id       TEXT,
    customer_id       TEXT,
    trigger_id        TEXT,
    send_as           TEXT        NOT NULL DEFAULT 'vera',
    turns             JSONB       NOT NULL DEFAULT '[]'::jsonb,
    auto_reply_count  INTEGER     NOT NULL DEFAULT 0,
    last_bot_body     TEXT,
    ended             BOOLEAN     NOT NULL DEFAULT FALSE,
    end_reason        TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversations_merchant_idx ON conversations (merchant_id);
CREATE INDEX IF NOT EXISTS conversations_customer_idx ON conversations (customer_id);
CREATE INDEX IF NOT EXISTS conversations_active_idx ON conversations (ended, updated_at DESC);

COMMENT ON TABLE conversations IS 'Per-conversation turn history + auto-reply counter + ended flag for reply state machine.';

-- ─── 3) suppressions ─────────────────────────────────────────────────────────
-- Per-merchant suppression keys with TTL. Prevents re-sending same trigger family.
CREATE TABLE IF NOT EXISTS suppressions (
    merchant_id      TEXT        NOT NULL,
    suppression_key  TEXT        NOT NULL,
    trigger_id       TEXT,
    expires_at       TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (merchant_id, suppression_key)
);

CREATE INDEX IF NOT EXISTS suppressions_expires_idx ON suppressions (expires_at);

COMMENT ON TABLE suppressions IS 'Suppression keys per merchant — bot refuses re-send while non-expired entry exists.';

-- ─── 4) blocked_merchants ────────────────────────────────────────────────────
-- Merchants that explicitly opted out (hostile reply / "stop"). All sends suppressed for TTL.
CREATE TABLE IF NOT EXISTS blocked_merchants (
    merchant_id  TEXT        PRIMARY KEY,
    reason       TEXT,
    expires_at   TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS blocked_merchants_expires_idx ON blocked_merchants (expires_at);

COMMENT ON TABLE blocked_merchants IS 'Merchants who said stop/not-interested. All sends blocked until expires_at.';

-- ─── housekeeping function: cleanup expired entries ─────────────────────────
-- Bot calls this periodically (or on startup). Optional.
CREATE OR REPLACE FUNCTION cleanup_expired_state()
RETURNS TABLE(suppressions_deleted INT, blocks_deleted INT) AS $$
DECLARE
    s_count INT;
    b_count INT;
BEGIN
    DELETE FROM suppressions WHERE expires_at < NOW();
    GET DIAGNOSTICS s_count = ROW_COUNT;

    DELETE FROM blocked_merchants WHERE expires_at < NOW();
    GET DIAGNOSTICS b_count = ROW_COUNT;

    RETURN QUERY SELECT s_count, b_count;
END;
$$ LANGUAGE plpgsql;

-- ─── verify ──────────────────────────────────────────────────────────────────
-- After running this script, verify with:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
-- Expected: contexts, conversations, suppressions, blocked_merchants
