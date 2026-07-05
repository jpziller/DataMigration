-- Returns 1 if the string is a plausible, Salesforce-acceptable email address.
IF OBJECT_ID('dbo.IsValidEmail', 'FN') IS NOT NULL
    DROP FUNCTION dbo.IsValidEmail;
GO

CREATE FUNCTION dbo.IsValidEmail(@Email VARCHAR(255))
RETURNS BIT
AS
BEGIN
    DECLARE @Valid BIT = 0
    DECLARE @AtPos INT
    IF @Email IS NULL RETURN 0

    SET @Email = LTRIM(RTRIM(LOWER(@Email)))
    SET @AtPos = CHARINDEX('@', @Email)

    IF @Email LIKE '[a-z0-9_-]%@[a-z0-9-]%.[a-z][a-z]%'
        AND LEN(@Email) > 1
        AND @Email NOT LIKE '%@%@%'
        AND CHARINDEX('.@', @Email) = 0
        AND CHARINDEX('..', @Email) = 0
        AND CHARINDEX('.', LEFT(@Email, 1)) = 0                       -- dot can't lead the local part
        AND @AtPos <> 0
        AND @AtPos < 65                                               -- local part <= 64 chars (RFC 5321)
        AND LEN(@Email) <= 80                                         -- Salesforce's email length cap
        AND RIGHT(@Email, 1) BETWEEN 'a' AND 'z'
        -- disallowed characters anywhere in the address (']' placed first so it's literal, not a class terminator)
        AND @Email NOT LIKE ('%[],;:[<>()"$ ' + CHAR(9) + ']%')
        -- disallowed characters in the domain part specifically
        AND SUBSTRING(@Email, @AtPos, LEN(@Email)) NOT LIKE '%[!#%&''*+/=?^_`{|}]%'
    BEGIN
        SET @Valid = 1
    END

    RETURN @Valid
END
GO
