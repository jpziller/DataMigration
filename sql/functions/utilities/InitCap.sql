-- Capitalizes the first letter of each word (word boundaries: space, punctuation).
IF OBJECT_ID('dbo.InitCap', 'FN') IS NOT NULL
    DROP FUNCTION dbo.InitCap;
GO

CREATE FUNCTION dbo.InitCap(@Input VARCHAR(4000))
RETURNS VARCHAR(4000)
AS
BEGIN
    DECLARE @Index INT = 1
    DECLARE @Char CHAR(1)
    DECLARE @PrevChar CHAR(1)
    DECLARE @Output VARCHAR(4000) = LOWER(@Input)

    WHILE @Index <= LEN(@Input)
    BEGIN
        SET @Char = SUBSTRING(@Input, @Index, 1)
        SET @PrevChar = CASE WHEN @Index = 1 THEN ' ' ELSE SUBSTRING(@Input, @Index - 1, 1) END

        IF @PrevChar IN (' ', ';', ':', '!', '?', ',', '.', '_', '-', '/', '&', '''', '(')
        BEGIN
            IF @PrevChar != '''' OR UPPER(@Char) != 'S'
                SET @Output = STUFF(@Output, @Index, 1, UPPER(@Char))
        END

        SET @Index = @Index + 1
    END

    RETURN @Output
END
GO
