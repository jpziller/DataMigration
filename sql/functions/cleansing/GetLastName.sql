-- Extracts the last name from a "Full Name" string, dropping a Mr/Mrs/Ms/Dr title
-- if present and keeping a Jr/Sr/II/III/IV suffix attached to the last name.
IF OBJECT_ID('dbo.GetLastName', 'FN') IS NOT NULL
    DROP FUNCTION dbo.GetLastName;
GO

CREATE FUNCTION dbo.GetLastName(@Input VARCHAR(100))
RETURNS VARCHAR(100)
AS
BEGIN
    DECLARE @Result VARCHAR(100)
    SET @Result = (
        SELECT
            CASE
                WHEN SUBSTRING(Split.Rest, 1 + CHARINDEX(' ', Split.Rest), LEN(Split.Rest)) IN ('jr', 'sr', 'II', 'III', 'IV')
                    THEN SUBSTRING(Split.Rest, 1, CHARINDEX(' ', Split.Rest) - 1) + ' ' +
                         SUBSTRING(Split.Rest, 1 + CHARINDEX(' ', Split.Rest), LEN(Split.Rest))
                WHEN SUBSTRING(Split.Rest, 1 + CHARINDEX(' ', Split.Rest), LEN(Split.Rest)) IS NULL THEN ''
                ELSE SUBSTRING(Split.Rest, 1 + CHARINDEX(' ', Split.Rest), LEN(Split.Rest))
            END
        FROM (
            SELECT
                CASE WHEN 0 = CHARINDEX(' ', NameNoTitle.Rest) THEN NameNoTitle.Rest
                     WHEN NameNoTitle.Rest IS NULL THEN '(Blank)'
                     ELSE SUBSTRING(NameNoTitle.Rest, CHARINDEX(' ', NameNoTitle.Rest) + 1, LEN(NameNoTitle.Rest))
                END AS Rest
            FROM (
                SELECT
                    CASE WHEN SUBSTRING(Normalized.FullName, 1, 3) IN ('MR ', 'MS ', 'DR ', 'MRS')
                         THEN LTRIM(RTRIM(SUBSTRING(Normalized.FullName, 4, LEN(Normalized.FullName))))
                         ELSE LTRIM(RTRIM(Normalized.FullName))
                    END AS Rest
                FROM (
                    SELECT REPLACE(REPLACE(REPLACE(REPLACE(LTRIM(RTRIM(@Input)), '  ', ' '), '  ', ' '), ',', ' '), '.', ' ') AS FullName
                ) AS Normalized
            ) AS NameNoTitle
        ) AS Split
    )
    RETURN @Result
END
GO
