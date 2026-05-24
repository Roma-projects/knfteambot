-- БД parser_kovorkingi_online (источник kovorkingi.online)
CREATE TABLE IF NOT EXISTS kovorkingi_online (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT,
    address TEXT,
    schedule TEXT,
    district TEXT NOT NULL DEFAULT 'все',
    city TEXT NOT NULL DEFAULT 'Екатеринбург'
);
