-- Extracts the first name from a "Full Name" string, dropping a Mr/Mrs/Ms/Dr title if present.
IF OBJECT_ID('dbo.GetFirstName', 'FN') IS NOT NULL
    DROP FUNCTION dbo.GetFirstName;
GO

CREATE FUNCTION dbo.GetFirstName(@Input VARCHAR(100))
RETURNS VARCHAR(100)
AS
BEGIN
    DECLARE @Result VARCHAR(100)
    SET @Result = (
        SELECT
            CASE WHEN 0 = CHARINDEX(' ', NameNoTitle.Rest)
                 THEN NameNoTitle.Rest
                 ELSE SUBSTRING(NameNoTitle.Rest, 1, CHARINDEX(' ', NameNoTitle.Rest) - 1)
            END
        FROM (
            SELECT
                CASE WHEN SUBSTRING(Normalized.FullName, 1, 3) IN ('MR ', 'MS ', 'DR ', 'MRS')
                     THEN LTRIM(RTRIM(SUBSTRING(Normalized.FullName, 4, LEN(Normalized.FullName))))
                     ELSE LTRIM(RTRIM(Normalized.FullName))
                END AS Rest
            FROM (
                -- Trim, and collapse repeated separators before splitting.
                SELECT REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(@Input)), '  ', ' '), '  ', ' '), ',', ' '), '.', ' ') AS FullName
            ) AS Normalized
        ) AS NameNoTitle
    )
    RETURN @Result
END
GO
