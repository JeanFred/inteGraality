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
