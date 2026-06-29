CREATE TABLE Account (
    id      INTEGER PRIMARY KEY,
    balance INTEGER NOT NULL
);
CREATE TABLE AuditLog (
    id     INTEGER PRIMARY KEY,
    msg    TEXT NOT NULL
);
CREATE TRIGGER trg_account_audit AFTER INSERT ON Account
BEGIN
    INSERT INTO AuditLog (msg) VALUES ('account created');
END;
