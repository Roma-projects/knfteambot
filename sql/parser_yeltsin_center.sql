-- Единая схема parser_yeltsin_center
CREATE TABLE IF NOT EXISTS events_yeltsin (
    id BIGSERIAL PRIMARY KEY,
    start_time TEXT,
    end_time TEXT,
    event_date DATE,
    city TEXT NOT NULL DEFAULT 'Екатеринбург',
    price TEXT NOT NULL DEFAULT 'Бесплатно',
    address TEXT,
    title TEXT,
    link TEXT,
    district TEXT NOT NULL DEFAULT 'все'
);
