-- Returns 1 if the given year is a leap year, 0 otherwise.
IF OBJECT_ID('dbo.IsLeapYear', 'FN') IS NOT NULL
    DROP FUNCTION dbo.IsLeapYear;
GO

CREATE FUNCTION dbo.IsLeapYear(@Year INT)
RETURNS BIT
AS
BEGIN
    RETURN CASE
        WHEN @Year % 400 = 0 THEN 1
        WHEN @Year % 100 = 0 THEN 0
        WHEN @Year % 4 = 0 THEN 1
        ELSE 0
    END
END
GO
