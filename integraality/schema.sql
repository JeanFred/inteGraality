CREATE TABLE IF NOT EXISTS wikis (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    UNIQUE KEY uq_hostname (hostname)
);

-- One row per wiki page (shared dimension for dashboards etc.).
CREATE TABLE IF NOT EXISTS pages (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    wiki_id INT UNSIGNED NOT NULL,
    page_id INT UNSIGNED NOT NULL,          -- MediaWiki page_id, stable across moves
    page_url VARCHAR(512) NOT NULL,
    page_title VARCHAR(255) NOT NULL,
    namespace_canonical VARCHAR(64) NOT NULL,
    namespace_localized VARCHAR(255) NOT NULL,
    root_page VARCHAR(255) NOT NULL,
    page_creator VARCHAR(255) DEFAULT NULL,
    page_created_at DATETIME DEFAULT NULL,
    UNIQUE KEY uq_wiki_page (wiki_id, page_id),
    FOREIGN KEY (wiki_id) REFERENCES wikis (id)
);

-- A page that is a dashboard (thin specialization of pages).
CREATE TABLE IF NOT EXISTS dashboards (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    page_pk INT UNSIGNED NOT NULL,
    UNIQUE KEY uq_page (page_pk),
    FOREIGN KEY (page_pk) REFERENCES pages (id)
);

CREATE TABLE IF NOT EXISTS dashboard_runs (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    dashboard_id INT UNSIGNED NOT NULL,
    wiki_id INT UNSIGNED NOT NULL,          -- denormalized for by-wiki queries
    finished_at DATETIME NOT NULL,
    duration_ms INT UNSIGNED DEFAULT NULL,
    status ENUM('OK', 'FAIL') NOT NULL,
    trigger_source ENUM('CRON', 'WEB') DEFAULT NULL,
    sparql_engine VARCHAR(32) DEFAULT NULL,
    error_category VARCHAR(32) DEFAULT NULL,
    error_detail TEXT DEFAULT NULL,
    -- Oldid the run produced (NULL if none), also the backfill idempotency key.
    revision_id INT UNSIGNED DEFAULT NULL,
    -- Output shape (not contents): population x rows x columns.
    entity_total INT UNSIGNED DEFAULT NULL,
    grouping_count INT UNSIGNED DEFAULT NULL,
    column_count INT UNSIGNED DEFAULT NULL,
    UNIQUE KEY uq_revision (revision_id),
    KEY idx_dashboard_finished (dashboard_id, finished_at),
    KEY idx_wiki_finished (wiki_id, finished_at),
    -- A failure must carry a category (an OK run may lack a revision_id).
    CONSTRAINT chk_fail_has_category CHECK (status <> 'FAIL' OR error_category IS NOT NULL),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards (id),
    FOREIGN KEY (wiki_id) REFERENCES wikis (id)
);
