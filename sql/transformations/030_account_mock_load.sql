/*  End-to-end pipeline smoke test: build Account_Load from Mockaroo-generated
    Account_Mock (dbo.Account_Mock, 100 rows via `generate-mock-data Account
    --count 100`) instead of a real source system.

    Account_Mock's schema is derived directly from Account's own describe()
    (mock_data.py only keeps createable fields), so every column here maps
    1:1 onto a real, writable Account field -- confirmed via `describe
    Account` and `auto-map` (47 Yes / 2 Review, both low-population address
    fields, not a naming mismatch). Column types/lengths below were pulled
    directly from Account_Mock's own INFORMATION_SCHEMA.COLUMNS.

    MigrationID__c came back from Mockaroo mock-generated too, and profiling
    showed only 99 distinct values across 100 rows (profile-sql-table
    Account_Mock) -- not safe as the unique insert key required by hard rule
    4. Rather than trust the mocked value, this generates a fresh one from
    LoadId (the local IDENTITY column), which is guaranteed unique.

    Load table carries:
      - LoadId : local IDENTITY key, used only for Id/Error writeback.
                 Excluded from the columns sent to Salesforce.
      - MigrationID__c : this org's real External ID field on Account
                 (confirmed via describe) -- guarantees a unique result
                 fingerprint on insert. Generated as 'MOCKACCT-<LoadId>',
                 not copied from the mocked source value.
      - every other Account_Mock column, unchanged.
      - Id, Error : populated by bulkops after the load.
*/
IF OBJECT_ID('dbo.Account_Load', 'U') IS NOT NULL
    DROP TABLE dbo.Account_Load;

CREATE TABLE dbo.Account_Load (
    LoadId                  INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    MigrationID__c          NVARCHAR(40)   NOT NULL,
    Name                    NVARCHAR(255)  NULL,
    Type                    NVARCHAR(255)  NULL,
    BillingStreet           NVARCHAR(MAX)  NULL,
    BillingCity             NVARCHAR(40)   NULL,
    BillingState            NVARCHAR(80)   NULL,
    BillingPostalCode       NVARCHAR(20)   NULL,
    BillingCountry          NVARCHAR(80)   NULL,
    BillingLatitude         DECIMAL(18,15) NULL,
    BillingLongitude        DECIMAL(18,15) NULL,
    BillingGeocodeAccuracy  NVARCHAR(40)   NULL,
    ShippingStreet          NVARCHAR(MAX)  NULL,
    ShippingCity            NVARCHAR(40)   NULL,
    ShippingState           NVARCHAR(80)   NULL,
    ShippingPostalCode      NVARCHAR(20)   NULL,
    ShippingCountry         NVARCHAR(80)   NULL,
    ShippingLatitude        DECIMAL(18,15) NULL,
    ShippingLongitude       DECIMAL(18,15) NULL,
    ShippingGeocodeAccuracy NVARCHAR(40)   NULL,
    Phone                   NVARCHAR(40)   NULL,
    Fax                     NVARCHAR(40)   NULL,
    AccountNumber           NVARCHAR(40)   NULL,
    Website                 NVARCHAR(255)  NULL,
    Sic                     NVARCHAR(20)   NULL,
    Industry                NVARCHAR(255)  NULL,
    AnnualRevenue           DECIMAL(18,0)  NULL,
    NumberOfEmployees       INT            NULL,
    Ownership               NVARCHAR(255)  NULL,
    TickerSymbol            NVARCHAR(20)   NULL,
    Description             NVARCHAR(MAX)  NULL,
    Rating                  NVARCHAR(255)  NULL,
    Site                    NVARCHAR(80)   NULL,
    SourceSystemIdentifier  NVARCHAR(85)   NULL,
    Jigsaw                  NVARCHAR(20)   NULL,
    CleanStatus             NVARCHAR(40)   NULL,
    AccountSource           NVARCHAR(255)  NULL,
    DunsNumber              NVARCHAR(9)    NULL,
    Tradestyle              NVARCHAR(255)  NULL,
    NaicsCode               NVARCHAR(8)    NULL,
    NaicsDesc               NVARCHAR(120)  NULL,
    YearStarted             NVARCHAR(4)    NULL,
    SicDesc                 NVARCHAR(80)   NULL,
    CustomerPriority__c     NVARCHAR(255)  NULL,
    SLA__c                  NVARCHAR(255)  NULL,
    Active__c               NVARCHAR(255)  NULL,
    NumberofLocations__c    DECIMAL(3,0)   NULL,
    UpsellOpportunity__c    NVARCHAR(255)  NULL,
    SLASerialNumber__c      NVARCHAR(10)   NULL,
    SLAExpirationDate__c    DATE           NULL,
    Id                      NVARCHAR(18)   NULL,   -- written back by bulkops
    Error                   NVARCHAR(MAX)  NULL    -- written back by bulkops
);

INSERT INTO dbo.Account_Load
    (MigrationID__c, Name, Type, BillingStreet, BillingCity, BillingState,
     BillingPostalCode, BillingCountry, BillingLatitude, BillingLongitude,
     BillingGeocodeAccuracy, ShippingStreet, ShippingCity, ShippingState,
     ShippingPostalCode, ShippingCountry, ShippingLatitude, ShippingLongitude,
     ShippingGeocodeAccuracy, Phone, Fax, AccountNumber, Website, Sic,
     Industry, AnnualRevenue, NumberOfEmployees, Ownership, TickerSymbol,
     Description, Rating, Site, SourceSystemIdentifier, Jigsaw, CleanStatus,
     AccountSource, DunsNumber, Tradestyle, NaicsCode, NaicsDesc, YearStarted,
     SicDesc, CustomerPriority__c, SLA__c, Active__c, NumberofLocations__c,
     UpsellOpportunity__c, SLASerialNumber__c, SLAExpirationDate__c)
SELECT
    CONCAT('MOCKACCT-', ROW_NUMBER() OVER (ORDER BY (SELECT NULL))),  -- guaranteed-unique, not the mocked value
    src.Name, src.Type, src.BillingStreet, src.BillingCity, src.BillingState,
    src.BillingPostalCode, src.BillingCountry, src.BillingLatitude, src.BillingLongitude,
    src.BillingGeocodeAccuracy, src.ShippingStreet, src.ShippingCity, src.ShippingState,
    src.ShippingPostalCode, src.ShippingCountry, src.ShippingLatitude, src.ShippingLongitude,
    src.ShippingGeocodeAccuracy, src.Phone, src.Fax, src.AccountNumber, src.Website, src.Sic,
    src.Industry, src.AnnualRevenue, src.NumberOfEmployees, src.Ownership, src.TickerSymbol,
    src.Description, src.Rating, src.Site, src.SourceSystemIdentifier, src.Jigsaw, src.CleanStatus,
    src.AccountSource, src.DunsNumber, src.Tradestyle, src.NaicsCode, src.NaicsDesc, src.YearStarted,
    src.SicDesc, src.CustomerPriority__c, src.SLA__c, src.Active__c, src.NumberofLocations__c,
    src.UpsellOpportunity__c, src.SLASerialNumber__c, src.SLAExpirationDate__c
FROM dbo.Account_Mock AS src;

/*  Then, from the shell:

    EXEC dbo.CheckLoadTableDuplicateKeys 'Account_Load', 'MigrationID__c'
    python cli.py bulkops Account insert Account_Load --key-column LoadId --email-deliverability no-access

    No [Sort] column needed (hard rule 6) -- Account_Mock has no parent
    lookup field at all; mock_data.py skips reference fields (ParentId,
    OwnerId, etc.) since there's no reasonable mock mapping for them.
*/
