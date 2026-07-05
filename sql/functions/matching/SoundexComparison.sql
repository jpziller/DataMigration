-- Compares two (FirstName, LastName) pairs using SQL Server's built-in
-- SOUNDEX(). Returns 1.0 for an exact soundex match, otherwise a ratio
-- that is NOT a bounded similarity score -- treat it as a rough signal,
-- not a percentage.
IF OBJECT_ID('dbo.SoundexComparison', 'FN') IS NOT NULL
    DROP FUNCTION dbo.SoundexComparison;
GO

CREATE FUNCTION dbo.SoundexComparison(@firstName1 VARCHAR(50), @lastName1 VARCHAR(50),
                                       @firstName2 VARCHAR(50), @lastName2 VARCHAR(50))
RETURNS FLOAT
AS
BEGIN
    DECLARE @soundex1 VARCHAR(8), @soundex2 VARCHAR(8)

    SET @soundex1 = SOUNDEX(@firstName1) + SOUNDEX(@lastName1)
    SET @soundex2 = SOUNDEX(@firstName2) + SOUNDEX(@lastName2)

    IF @soundex1 = @soundex2
        RETURN 1.0

    IF SOUNDEX(@firstName2 + ' ' + @lastName2) = 0
        RETURN 0.0

    RETURN CAST(SOUNDEX(@firstName1 + ' ' + @lastName1) AS FLOAT) / CAST(SOUNDEX(@firstName2 + ' ' + @lastName2) AS FLOAT)
END
GO
