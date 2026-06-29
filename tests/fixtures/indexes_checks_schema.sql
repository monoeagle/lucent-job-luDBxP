CREATE TABLE Person (
    id     INTEGER PRIMARY KEY,
    email  TEXT NOT NULL,
    age    INTEGER CHECK (age >= 0),
    region TEXT,
    CONSTRAINT ck_email CHECK (email LIKE '%@%')
);
CREATE INDEX ix_person_region ON Person(region);
CREATE UNIQUE INDEX ux_person_email ON Person(email);
