-- Strips all non-numeric characters from a string, returning only digits.
IF OBJECT_ID('dbo.CleanNumber', 'FN') IS NOT NULL
    DROP FUNCTION dbo.CleanNumber;
GO

CREATE FUNCTION dbo.CleanNumber(@Input VARCHAR(MAX))
RETURNS VARCHAR(100)
AS
BEGIN
    DECLARE @Result VARCHAR(100) = ''
    DECLARE @Position INT = 1
    WHILE @Position <= LEN(@Input)
    BEGIN
        IF SUBSTRING(@Input, @Position, 1) LIKE '[0-9]'
            SET @Result = @Result + SUBSTRING(@Input, @Position, 1)
        SET @Position = @Position + 1
    END
    RETURN LTRIM(RTRIM(@Result))
END
GO
