-- Returns the number of whole calendar months between two dates.
IF OBJECT_ID('dbo.GetMonthsBetweenDates', 'FN') IS NOT NULL
    DROP FUNCTION dbo.GetMonthsBetweenDates;
GO

CREATE FUNCTION dbo.GetMonthsBetweenDates(@StartDate DATE, @EndDate DATE)
RETURNS INT
AS
BEGIN
    RETURN DATEDIFF(MONTH, @StartDate, DATEADD(DAY, 1, @EndDate))
END
GO
