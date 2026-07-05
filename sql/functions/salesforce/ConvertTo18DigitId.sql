-- Converts a case-sensitive 15-character Salesforce Id to its case-safe
-- 18-character form. Algorithm: for each 5-character chunk of the input,
-- build a 5-bit flag of which characters are uppercase letters, then map
-- that value to a checksum character (0-25 -> A-Z, 26-31 -> 0-5). This is
-- Salesforce's published Id-conversion spec, independently implemented.
IF OBJECT_ID('dbo.ConvertTo18DigitId', 'FN') IS NOT NULL
    DROP FUNCTION dbo.ConvertTo18DigitId;
GO

CREATE FUNCTION dbo.ConvertTo18DigitId(@Id15 CHAR(15))
RETURNS CHAR(18)
AS
BEGIN
    DECLARE @Suffix VARCHAR(3) = ''
    DECLARE @Chunk INT = 0
    DECLARE @Value INT
    DECLARE @CharPos INT
    DECLARE @ThisChar CHAR(1)

    WHILE @Chunk < 3
    BEGIN
        SET @Value = 0
        SET @CharPos = 0
        WHILE @CharPos < 5
        BEGIN
            SET @ThisChar = SUBSTRING(@Id15, @Chunk * 5 + @CharPos + 1, 1)
            IF ASCII(@ThisChar) BETWEEN 65 AND 90 -- A-Z
                SET @Value = @Value + POWER(2, @CharPos)
            SET @CharPos = @CharPos + 1
        END
        SET @Suffix = @Suffix + SUBSTRING('ABCDEFGHIJKLMNOPQRSTUVWXYZ012345', @Value + 1, 1)
        SET @Chunk = @Chunk + 1
    END

    RETURN @Id15 + @Suffix
END
GO
