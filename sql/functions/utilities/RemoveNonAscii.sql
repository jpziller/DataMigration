-- Removes non-printable and non-ASCII characters, keeping printable range 32-255.
IF OBJECT_ID('dbo.RemoveNonAscii', 'FN') IS NOT NULL
    DROP FUNCTION dbo.RemoveNonAscii;
GO

CREATE FUNCTION dbo.RemoveNonAscii(@Input NVARCHAR(MAX))
RETURNS VARCHAR(MAX)
AS
BEGIN
    DECLARE @Result VARCHAR(MAX) = ''
    DECLARE @Position INT = 1
    WHILE @Position <= LEN(@Input)
    BEGIN
        IF UNICODE(SUBSTRING(@Input, @Position, 1)) BETWEEN 32 AND 255
            SET @Result = @Result + SUBSTRING(@Input, @Position, 1)
        SET @Position = @Position + 1
    END
    RETURN @Result
END
GO
