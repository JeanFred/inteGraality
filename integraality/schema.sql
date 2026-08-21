CREATE TABLE IF NOT EXISTS dashboards (
    page_title VARCHAR(255) NOT NULL,
    site_url VARCHAR(255) NOT NULL DEFAULT 'https://www.wikidata.org/wiki/',
    PRIMARY KEY (page_title, site_url)
);
