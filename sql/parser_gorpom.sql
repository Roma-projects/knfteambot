-- БД parser_gorpom (источник gorpom.ru, коворкинги Екатеринбург)
CREATE TABLE IF NOT EXISTS coworkings_gorpom (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT,
    address TEXT,
    schedule TEXT,
    district TEXT NOT NULL DEFAULT 'все',
    city TEXT NOT NULL DEFAULT 'Екатеринбург'
);
