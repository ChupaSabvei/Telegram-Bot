-- Feature 002: survey flow columns + favorites table

ALTER TABLE events ADD COLUMN activity_slug VARCHAR(32);
ALTER TABLE events ADD COLUMN venue_format VARCHAR(16) DEFAULT 'unknown' NOT NULL;
ALTER TABLE events ADD COLUMN price_amount_rub INTEGER;
ALTER TABLE events ADD COLUMN audience_tags JSON DEFAULT '[]' NOT NULL;
ALTER TABLE events ADD COLUMN address VARCHAR(500);
ALTER TABLE events ADD COLUMN popularity_score INTEGER DEFAULT 0 NOT NULL;

CREATE TABLE IF NOT EXISTS favorites (
    id VARCHAR(36) PRIMARY KEY,
    telegram_id BIGINT NOT NULL,
    event_id VARCHAR(36) NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    saved_at TIMESTAMP NOT NULL,
    UNIQUE (telegram_id, event_id)
);

CREATE INDEX IF NOT EXISTS ix_events_city_activity_start ON events (city_slug, activity_slug, start_at);
CREATE INDEX IF NOT EXISTS ix_favorites_telegram_saved ON favorites (telegram_id, saved_at);
