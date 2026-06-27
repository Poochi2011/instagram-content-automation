-- SQLite schema for Instagram Content Automation.
--
-- Design note: "posts" doubles as the processed-posts and download-history
-- table via its status/timestamp columns, instead of three overlapping
-- tables tracking the same row's lifecycle. Keeps the schema simple while
-- still satisfying "never process duplicates" (shortcode is UNIQUE).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT,
    last_post_shortcode TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    shortcode       TEXT NOT NULL UNIQUE,
    post_url        TEXT NOT NULL,
    caption         TEXT,
    posted_at       TEXT,
    image_path      TEXT,
    ocr_text        TEXT,
    repost_caption  TEXT,
    is_carousel     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'new'
                    CHECK (status IN ('new', 'downloaded', 'ocr_done', 'ready', 'processed', 'error')),
    downloaded_at   TEXT,
    processed_at    TEXT,
    -- Publish-pipeline state (Graph API auto-publish). Kept on the row, not in
    -- memory, so a daemon/Actions restart resumes retries exactly where it left off.
    publish_attempts       INTEGER NOT NULL DEFAULT 0,
    last_publish_error     TEXT,
    next_publish_attempt_at TEXT,
    published_at            TEXT,
    ig_media_id              TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_posts_account_id ON posts(account_id);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status);

-- Additional slides for carousel (GraphSidecar) posts. Position 0 is the cover
-- slide and is also mirrored in posts.image_path for backward compatibility
-- with the single-image OCR/dashboard code paths.
CREATE TABLE IF NOT EXISTS post_media (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id     INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    image_path  TEXT NOT NULL,
    is_video    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (post_id, position)
);

CREATE INDEX IF NOT EXISTS idx_post_media_post_id ON post_media(post_id);

CREATE TABLE IF NOT EXISTS errors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT NOT NULL,
    message      TEXT NOT NULL,
    account_username TEXT,
    occurred_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
