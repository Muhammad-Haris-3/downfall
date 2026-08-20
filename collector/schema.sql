-- Shortfall collection store.
--
-- We do NOT keep snapshots. A snapshot every 70s across 2,508 stations is
-- ~3.1M rows a day and answers no question we actually ask. What we need is
-- when a station STOPPED being usable and when it started again, so that is
-- what is stored: one row per outage, opened when it starts and closed when it
-- ends. Roughly four orders of magnitude smaller, and it is the exact object
-- the censoring analysis consumes.

CREATE TABLE IF NOT EXISTS stations (
    station_id   TEXT PRIMARY KEY,
    name         TEXT,
    lat          REAL,
    lon          REAL,
    capacity     INTEGER,
    first_seen   INTEGER NOT NULL,
    last_seen    INTEGER NOT NULL
);

-- kind:
--   empty   no bikes to take
--   full    no docks to return to
--   offline station not installed / not renting - absent, which is not the
--           same as empty and must never be pooled with it
CREATE TABLE IF NOT EXISTS outages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id  TEXT    NOT NULL REFERENCES stations(station_id),
    kind        TEXT    NOT NULL CHECK (kind IN ('empty','full','offline')),
    start_ts    INTEGER NOT NULL,         -- feed's own clock (last_reported)
    end_ts      INTEGER,                  -- NULL while still ongoing
    start_run   TEXT    NOT NULL,
    end_run     TEXT,
    -- True when the outage was already underway at the moment collection began,
    -- so its real start is unknown. Left-censored: it must not be counted as a
    -- duration, only as "at least this long".
    left_open   INTEGER NOT NULL DEFAULT 0,
    -- True when the outage ended at some unknown moment while we were not
    -- collecting. We know it ended; we do NOT know when. Recording a guess as
    -- if it were an observation is exactly the failure this column prevents.
    end_unknown INTEGER NOT NULL DEFAULT 0,
    CHECK (end_ts IS NULL OR end_ts >= start_ts)
);

CREATE INDEX IF NOT EXISTS idx_outages_open    ON outages(station_id, kind) WHERE end_ts IS NULL;
CREATE INDEX IF NOT EXISTS idx_outages_station ON outages(station_id, start_ts);

-- Coverage. A gap in collection must never read as a period with no outages,
-- so every run records what it actually managed to observe.
CREATE TABLE IF NOT EXISTS runs (
    run_id       TEXT PRIMARY KEY,
    started_wall INTEGER NOT NULL,
    ended_wall   INTEGER,
    files_seen   INTEGER NOT NULL DEFAULT 0,  -- distinct published files
    requests     INTEGER NOT NULL DEFAULT 0,
    not_modified INTEGER NOT NULL DEFAULT 0,  -- ETag hits: nothing new to fetch
    errors       INTEGER NOT NULL DEFAULT 0,
    note         TEXT
);
