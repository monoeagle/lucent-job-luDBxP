CREATE TABLE Parent (
    ParentID INTEGER PRIMARY KEY,
    Label TEXT NOT NULL
);
CREATE TABLE Profile (
    ProfileID INTEGER PRIMARY KEY,
    ParentID INTEGER NOT NULL REFERENCES Parent(ParentID),
    Bio TEXT
);
CREATE UNIQUE INDEX ux_profile_parent ON Profile(ParentID);
CREATE TABLE Note (
    NoteID INTEGER PRIMARY KEY,
    ParentID INTEGER NOT NULL REFERENCES Parent(ParentID),
    Body TEXT
);
CREATE UNIQUE INDEX ux_note_parent_partial ON Note(ParentID) WHERE Body IS NOT NULL;
