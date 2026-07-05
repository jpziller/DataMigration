-- Adds/refreshes an integer [Sort] column on a load table, numbered by
-- ROW_NUMBER() OVER (ORDER BY <parent key column>), so every row sharing the
-- same parent lands in a contiguous Sort range. bulkops.py orders by [Sort]
-- when present, so parent/child rows stay together in the same submitted
-- batch instead of being scattered across batches that process concurrently
-- and lock-contend on the shared parent record.
--
-- Also returns a verification result set: any parent key where
-- MAX(Sort) - MIN(Sort) <> COUNT(*) - 1 has its rows split across a
-- non-contiguous range (should be empty for a clean sort).
--
-- Usage: EXEC dbo.AddBulkLoadSortColumn 'OrderItem_Load', 'OrderId';
IF OBJECT_ID('dbo.AddBulkLoadSortColumn', 'P') IS NOT NULL
    DROP PROCEDURE dbo.AddBulkLoadSortColumn;
GO

CREATE PROCEDURE dbo.AddBulkLoadSortColumn
    @TableName NVARCHAR(128),
    @ParentKeyColumn NVARCHAR(128),
    @Schema NVARCHAR(128) = 'dbo'
AS
BEGIN
    SET NOCOUNT ON
    DECLARE @Sql NVARCHAR(MAX)

    IF COL_LENGTH(@Schema + '.' + @TableName, 'Sort') IS NULL
    BEGIN
        SET @Sql = N'ALTER TABLE [' + @Schema + N'].[' + @TableName + N'] ADD [Sort] INT NULL;'
        EXEC sp_executesql @Sql
    END

    SET @Sql = N'
        WITH NumberedRows AS (
            SELECT [Sort], ROW_NUMBER() OVER (ORDER BY [' + @ParentKeyColumn + N']) AS RowNum
            FROM [' + @Schema + N'].[' + @TableName + N']
        )
        UPDATE NumberedRows SET [Sort] = RowNum;'
    EXEC sp_executesql @Sql

    SET @Sql = N'
        SELECT [' + @ParentKeyColumn + N'] AS ParentKey,
               MIN([Sort]) AS MinSort, MAX([Sort]) AS MaxSort, COUNT(*) AS RowCount,
               MAX([Sort]) - MIN([Sort]) AS SortSpan
        FROM [' + @Schema + N'].[' + @TableName + N']
        GROUP BY [' + @ParentKeyColumn + N']
        HAVING MAX([Sort]) - MIN([Sort]) <> COUNT(*) - 1;'
    EXEC sp_executesql @Sql
END
GO
