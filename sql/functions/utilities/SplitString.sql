-- Splits a delimited string into a table of items (one row per item).
IF OBJECT_ID('dbo.SplitString', 'TF') IS NOT NULL
    DROP FUNCTION dbo.SplitString;
GO

CREATE FUNCTION dbo.SplitString(@Input NVARCHAR(MAX), @Delimiter CHAR(1))
RETURNS @Output TABLE (Item NVARCHAR(1000))
AS
BEGIN
    DECLARE @StartIndex INT = 1, @EndIndex INT

    IF SUBSTRING(@Input, LEN(@Input), 1) <> @Delimiter
        SET @Input = @Input + @Delimiter

    WHILE CHARINDEX(@Delimiter, @Input) > 0
    BEGIN
        SET @EndIndex = CHARINDEX(@Delimiter, @Input)
        INSERT INTO @Output (Item)
        SELECT SUBSTRING(@Input, @StartIndex, @EndIndex - 1)
        SET @Input = SUBSTRING(@Input, @EndIndex + 1, LEN(@Input))
    END

    RETURN
END
GO
