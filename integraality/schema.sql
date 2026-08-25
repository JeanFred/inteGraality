CREATE TABLE IF NOT EXISTS wikis (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
    UNIQUE KEY uq_hostname (hostname)
);

CREATE TABLE IF NOT EXISTS dashboards (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    wiki_id INT UNSIGNED NOT NULL,
    page_id INT UNSIGNED NOT NULL,
    page_url VARCHAR(512) NOT NULL,
    page_title VARCHAR(255) NOT NULL,
    namespace_canonical VARCHAR(64) NOT NULL,
    namespace_localized VARCHAR(255) NOT NULL,
    root_page VARCHAR(255) NOT NULL,
    page_creator VARCHAR(255) DEFAULT NULL,
    page_created_at DATETIME DEFAULT NULL,
    -- uq_wiki_page leads with wiki_id, so it also serves as the index the
    -- FK requires and as the index for wiki_id lookups/filters. Keep wiki_id
    -- first, else reordering would force a separate index on wiki_id for the FK.
    UNIQUE KEY uq_wiki_page (wiki_id, page_id),
    FOREIGN KEY (wiki_id) REFERENCES wikis (id)
);
