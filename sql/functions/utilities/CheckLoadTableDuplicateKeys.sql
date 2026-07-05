-- Checks a load table's migration-key column for duplicate or missing values
-- before bulkops. A duplicate (or NULL) migration key breaks fingerprint-
-- based result mapping on insert (see bulkops.py) -- Bulk API 2.0 echoes back
-- the sent columns with no row-order guarantee, so two rows with an
-- identical migration key produce an identical fingerprint and can't be told
-- apart when writing Id/Error back. Either a genuine duplicate legacy record
-- or a transform bug -- resolve it before loading, don't let it surface only
-- as an "ambiguous" count after a real Salesforce API call.
--
-- Returns two result sets:
--   1. Duplicated key values with their occurrence count.
--   2. A single row with the count of NULL/missing keys (multiple NULLs
--      collide the same way a duplicate value would).
-- Both empty = clean to load.
--
-- Usage: EXEC dbo.CheckLoadTableDuplicateKeys 'Account_Load', 'Migrated_Id__c';
IF OBJECT_ID('dbo.CheckLoadTableDuplicateKeys', 'P') IS NOT NULL
    DROP PROCEDURE dbo.CheckLoadTableDuplicateKeys;
GO

CREATE PROCEDURE dbo.CheckLoadTableDuplicateKeys
    @TableName NVARCHAR(128),
    @KeyColumn NVARCHAR(128),
    @Schema NVARCHAR(128) = 'dbo'
AS
BEGIN
    SET NOCOUNT ON
    DECLARE @Sql NVARCHAR(MAX)

    SET @Sql = N'
        SELECT [' + @KeyColumn + N'] AS DuplicateKey, COUNT(*) AS Occurrences
        FROM [' + @Schema + N'].[' + @TableName + N']
        WHERE [' + @KeyColumn + N'] IS NOT NULL
        GROUP BY [' + @KeyColumn + N']
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC;'
    EXEC sp_executesql @Sql

    SET @Sql = N'
        SELECT COUNT(*) AS RowsWithMissingKey
        FROM [' + @Schema + N'].[' + @TableName + N']
        WHERE [' + @KeyColumn + N'] IS NULL;'
    EXEC sp_executesql @Sql
END
GO
