-- Expands common address abbreviations (ave->avenue, blvd->boulevard, etc.)
-- for more consistent address matching/dedup.
IF OBJECT_ID('dbo.CleanPostalAddress', 'FN') IS NOT NULL
    DROP FUNCTION dbo.CleanPostalAddress;
GO

CREATE FUNCTION dbo.CleanPostalAddress(@Address VARCHAR(255))
RETURNS VARCHAR(255)
AS
BEGIN
    IF @Address IS NULL RETURN NULL

    SET @Address = REPLACE(@Address, '.ave', 'avenue')
    SET @Address = REPLACE(@Address, 'ave', 'avenue')
    SET @Address = REPLACE(@Address, '.ltd', 'limited')
    SET @Address = REPLACE(@Address, 'ltd', 'limited')
    SET @Address = REPLACE(@Address, '.rd', 'road')
    SET @Address = REPLACE(@Address, 'rd', 'road')
    SET @Address = REPLACE(@Address, 'twr', 'tower')
    SET @Address = REPLACE(@Address, '.plc', 'place')
    SET @Address = REPLACE(@Address, 'plc', 'place')
    SET @Address = REPLACE(@Address, '.blvd', 'boulevard')
    SET @Address = REPLACE(@Address, 'blvd', 'boulevard')
    SET @Address = REPLACE(@Address, '.crt', 'court')
    SET @Address = REPLACE(@Address, 'crt', 'court')
    SET @Address = REPLACE(@Address, '.est', 'estate')
    SET @Address = REPLACE(@Address, 'est', 'estate')
    SET @Address = REPLACE(@Address, '.hse', 'house')
    SET @Address = REPLACE(@Address, 'hse', 'house')
    SET @Address = REPLACE(@Address, '.st', 'street')
    SET @Address = REPLACE(@Address, 'st', 'street')
    SET @Address = REPLACE(@Address, 'lvl', 'level')
    SET @Address = REPLACE(@Address, 'inc.', 'incorporated')
    SET @Address = REPLACE(@Address, 'inc', 'incorporated')
    SET @Address = REPLACE(@Address, '.corp', 'corporation')
    SET @Address = REPLACE(@Address, 'corp', 'corporation')
    SET @Address = REPLACE(@Address, 'int', 'international')
    SET @Address = REPLACE(@Address, 'gmbh', 'GmbH')
    SET @Address = REPLACE(@Address, 'ges mbh', 'GmbH')
    SET @Address = REPLACE(@Address, 'm b h', 'mbh')

    RETURN @Address
END
GO
