/*  Example transform: build Account_Load from replicated source tables.

    The load table carries:
      - LoadId : a local unique key (IDENTITY) used ONLY for result writeback.
                 It is NOT sent to Salesforce (bulkops excludes it on insert).
      - Legacy_Id__c : the source system's primary key, mapped to a real SF
                 external-id text field. This guarantees a unique result
                 fingerprint on insert and makes re-runs idempotent via upsert.
      - the mapped Salesforce fields.
      - Id, Error : populated by bulkops after the load.

    Keep this file (and the whole sql/ tree) in GitHub. This is your
    migration's source of truth.
*/
IF OBJECT_ID('dbo.Account_Load', 'U') IS NOT NULL
    DROP TABLE dbo.Account_Load;

CREATE TABLE dbo.Account_Load (
    LoadId          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    Legacy_Id__c    NVARCHAR(50)  NOT NULL,   -- source PK -> SF external id
    Name            NVARCHAR(255) NOT NULL,
    Phone           NVARCHAR(40)  NULL,       -- e.g. dbo.fn_NormalizePhoneToE164
    BillingStreet   NVARCHAR(255) NULL,
    BillingCity     NVARCHAR(40)  NULL,
    BillingState    NVARCHAR(80)  NULL,
    BillingPostalCode NVARCHAR(20) NULL,
    Id              NVARCHAR(18)  NULL,       -- written back by bulkops
    Error           NVARCHAR(MAX) NULL        -- written back by bulkops
);

INSERT INTO dbo.Account_Load
    (Legacy_Id__c, Name, Phone, BillingStreet, BillingCity, BillingState, BillingPostalCode)
SELECT
    src.legacy_account_id,
    src.account_name,
    dbo.fn_NormalizePhoneToE164(src.main_phone),
    src.addr_line1,
    src.city,
    src.state_code,
    src.zip
FROM dbo.SourceAccounts AS src
WHERE src.is_active = 1;

/*  Then, from the shell:

    python cli.py bulkops Account upsert Account_Load --external-id Legacy_Id__c

    Re-running is safe: upsert on Legacy_Id__c updates rather than duplicating,
    and Id / Error are refreshed each run.
*/
