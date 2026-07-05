-- Replaces XML-invalid control characters (Unicode < 32, excluding tab/LF/CR)
-- with a replacement character, so a string is safe to embed in XML/CDATA.
IF OBJECT_ID('dbo.RemoveInvalidXmlChars', 'FN') IS NOT NULL
    DROP FUNCTION dbo.RemoveInvalidXmlChars;
GO

CREATE FUNCTION dbo.RemoveInvalidXmlChars(@Input NVARCHAR(MAX), @ReplaceWith NVARCHAR(1) = '')
RETURNS NVARCHAR(MAX)
AS
BEGIN
    DECLARE @Result NVARCHAR(MAX) = ''
    DECLARE @Position INT = 1
    DECLARE @Char NVARCHAR(1)

    WHILE @Position <= LEN(@Input)
    BEGIN
        SET @Char = SUBSTRING(@Input, @Position, 1)
        IF UNICODE(@Char) < 32 AND UNICODE(@Char) NOT IN (9, 10, 13)
            SET @Result = @Result + @ReplaceWith
        ELSE
            SET @Result = @Result + @Char
        SET @Position = @Position + 1
    END

    RETURN @Result
END
GO
