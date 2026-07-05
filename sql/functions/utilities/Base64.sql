-- Base64 encode/decode via SQL Server's built-in XML binary conversion.
IF OBJECT_ID('dbo.ToBase64', 'FN') IS NOT NULL
    DROP FUNCTION dbo.ToBase64;
GO

CREATE FUNCTION dbo.ToBase64(@Input VARCHAR(MAX))
RETURNS VARCHAR(MAX)
AS
BEGIN
    RETURN (
        SELECT CAST(N'' AS XML).value(
            'xs:base64Binary(xs:hexBinary(sql:column("bin")))', 'VARCHAR(MAX)'
        )
        FROM (SELECT CAST(@Input AS VARBINARY(MAX)) AS bin) AS b
    )
END
GO

IF OBJECT_ID('dbo.FromBase64', 'FN') IS NOT NULL
    DROP FUNCTION dbo.FromBase64;
GO

CREATE FUNCTION dbo.FromBase64(@Input VARCHAR(MAX))
RETURNS VARCHAR(MAX)
AS
BEGIN
    RETURN CAST(
        CAST(N'' AS XML).value('xs:base64Binary(sql:variable("@Input"))', 'VARBINARY(MAX)')
        AS VARCHAR(MAX)
    )
END
GO
