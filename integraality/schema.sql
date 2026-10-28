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

-- Append-only config history: one row per distinct config per dashboard,
-- keyed (dashboard_id, config_hash). Written when the hash changes.
CREATE TABLE IF NOT EXISTS dashboard_configurations (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    dashboard_id INT UNSIGNED NOT NULL,
    config_hash CHAR(64) NOT NULL,
    -- Provenance of the authoring revision that introduced this config.
    introduced_by_rev_id INT UNSIGNED DEFAULT NULL,
    introduced_at DATETIME DEFAULT NULL,
    author VARCHAR(255) DEFAULT NULL,
    -- Selector.
    selector_sparql TEXT NOT NULL,                   -- verbatim ground truth
    selector_mentions VARCHAR(512) DEFAULT NULL,     -- canonical comma-padded token bag ",P31,Q7889,"
    -- Grouping dimension.
    grouping_predicate VARCHAR(255) NOT NULL,        -- verbatim, e.g. "wdt:P21", "^schema:about"
    grouping_property VARCHAR(16) DEFAULT NULL,      -- plain P-id for simple wdt:Pnnn, else NULL (syntactic)
    grouping_type VARCHAR(16) DEFAULT NULL,          -- item|year|sitelink, resolved live, write-once
    grouping_threshold INT UNSIGNED NOT NULL,
    higher_grouping VARCHAR(255) DEFAULT NULL,
    explicit_groupings VARCHAR(512) DEFAULT NULL,    -- canonical comma-padded bag of RAW groupings tokens, NULL = none
    -- Flags / shape.
    row_totals BOOL NOT NULL,
    row_no_group BOOL NOT NULL,
    grouping_link_mode VARCHAR(16) NOT NULL,
    UNIQUE KEY uq_dashboard_config (dashboard_id, config_hash),
    KEY idx_grouping_property (grouping_property),
    KEY idx_grouping_type (grouping_type),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards (id)
);

-- Expanded concrete columns of a configuration, in post-expansion order.
CREATE TABLE IF NOT EXISTS dashboard_configuration_columns (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    configuration_id INT UNSIGNED NOT NULL,
    position INT UNSIGNED NOT NULL,
    column_type VARCHAR(16) NOT NULL,                 -- property|qualifier|reference|label|description|sitelink
    property_id VARCHAR(16) DEFAULT NULL,             -- tracked property, NULL for label/description/sitelink
    qualifier_id VARCHAR(16) DEFAULT NULL,            -- pq: qualifier property, NULL if not qualifier-scoped
    value VARCHAR(255) DEFAULT NULL,                  -- verbatim value scope incl. ~traversal, NULL if unscoped
    value_item VARCHAR(16) DEFAULT NULL,              -- bare Q-id of the value scope (facetable), NULL for literals
    value_traversal VARCHAR(16) DEFAULT NULL,         -- value path suffix: property+quantifier e.g. "P279*", else NULL
    reference_check_kind VARCHAR(16) DEFAULT NULL,    -- any|good|property|any_of|all_of, NULL if not a ref column
    reference_check_tokens VARCHAR(255) DEFAULT NULL, -- comma-padded atom bag (S<p>[=Q<v>]), NULL for any/good
    source_property VARCHAR(16) DEFAULT NULL,         -- P1234 for sourced columns, else NULL
    source_item VARCHAR(16) DEFAULT NULL,             -- Q567 for sourced columns, else NULL
    language VARCHAR(32) DEFAULT NULL,                -- label/description facet
    project VARCHAR(64) DEFAULT NULL,                 -- sitelink facet
    raw_key VARCHAR(255) NOT NULL,                    -- column.get_key(): lossless ground truth
    KEY idx_column_type (column_type),
    KEY idx_property_id (property_id),
    KEY idx_qualifier_id (qualifier_id),
    KEY idx_value_item (value_item),
    KEY idx_reference_check_kind (reference_check_kind),
    -- source_item is indexed (not source_property) because the feature reader
    -- exposes a "sourced from" filter on it. Add idx_source_property only if a
    -- query ever needs it.
    KEY idx_source_item (source_item),
    KEY idx_language (language),
    KEY idx_project (project),
    -- CASCADE (the only one): config rows are not deleted in normal operation,
    -- but a manual cleanup should not orphan column rows.
    FOREIGN KEY (configuration_id)
    REFERENCES dashboard_configurations (id) ON DELETE CASCADE
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
    configuration_id INT UNSIGNED DEFAULT NULL,  -- The config this run executed (NULL for historical/unlinked runs).
    UNIQUE KEY uq_revision (revision_id),
    KEY idx_dashboard_finished (dashboard_id, finished_at),
    KEY idx_wiki_finished (wiki_id, finished_at),
    KEY idx_run_configuration (configuration_id),
    -- A failure must carry a category (an OK run may lack a revision_id).
    CONSTRAINT chk_fail_has_category CHECK (status <> 'FAIL' OR error_category IS NOT NULL),
    FOREIGN KEY (dashboard_id) REFERENCES dashboards (id),
    FOREIGN KEY (wiki_id) REFERENCES wikis (id),
    FOREIGN KEY (configuration_id) REFERENCES dashboard_configurations (id)
);
