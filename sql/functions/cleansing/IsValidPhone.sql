-- Validates a phone number's area code / number length against a per-country
-- pattern table. Requires a reference table with this shape:
--
--   CREATE TABLE dbo.CountryPhoneNumberPattern (
--       CountryISDCode VARCHAR(5)  NOT NULL,   -- e.g. '1' for US/Canada
--       MinAreaCode    INT NOT NULL,
--       MaxAreaCode    INT NOT NULL,
--       MinPhoneNumber INT NOT NULL,
--       MaxPhoneNumber INT NOT NULL
--   );
--
-- Returns: 1 = valid, 0 = invalid, 2 = insufficient input to judge.
IF OBJECT_ID('dbo.IsValidPhone', 'FN') IS NOT NULL
    DROP FUNCTION dbo.IsValidPhone;
GO

CREATE FUNCTION dbo.IsValidPhone(@CountryCode VARCHAR(5), @AreaCode VARCHAR(10), @PhoneNumber VARCHAR(15))
RETURNS INT
AS
BEGIN
    DECLARE @ReturnValue INT
    DECLARE @MinAreaCode INT = 0, @MaxAreaCode INT = 0
    DECLARE @MinPhoneNumber INT = 0, @MaxPhoneNumber INT = 0
    DECLARE @MatchedCode VARCHAR(MAX)

    -- Strip leading zeros from country/area code before lookup.
    SET @CountryCode = REPLACE(LTRIM(REPLACE(@CountryCode, '0', ' ')), ' ', '0')
    SET @AreaCode = REPLACE(LTRIM(REPLACE(@AreaCode, '0', ' ')), ' ', '0')

    IF (LEN(@CountryCode) = 0 OR LEN(@AreaCode) = 0 OR LEN(@PhoneNumber) = 0)
    BEGIN
        SET @ReturnValue = 2
    END
    ELSE
    BEGIN
        SELECT @MatchedCode = CountryISDCode, @MinAreaCode = MinAreaCode, @MaxAreaCode = MaxAreaCode,
               @MinPhoneNumber = MinPhoneNumber, @MaxPhoneNumber = MaxPhoneNumber
        FROM dbo.CountryPhoneNumberPattern
        WHERE CountryISDCode = @CountryCode

        IF @MatchedCode IS NOT NULL
        BEGIN
            IF (LEN(@AreaCode) BETWEEN @MinAreaCode AND @MaxAreaCode
                AND LEN(@PhoneNumber) BETWEEN @MinPhoneNumber AND @MaxPhoneNumber)
                SET @ReturnValue = 1
            ELSE
                SET @ReturnValue = 0
        END
    END

    RETURN @ReturnValue
END
GO
