-- Returns 1 if the input string is a valid integer, 0 otherwise.
IF OBJECT_ID('dbo.IsInt', 'FN') IS NOT NULL
    DROP FUNCTION dbo.IsInt;
GO

CREATE FUNCTION dbo.IsInt(@Input VARCHAR(20))
RETURNS BIT
AS
BEGIN
    RETURN ISNUMERIC(REPLACE(REPLACE(@Input, '+', 'A'), '-', 'A') + '.0e0')
END
GO
