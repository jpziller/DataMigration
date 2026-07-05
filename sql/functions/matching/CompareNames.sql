-- Naive character-position similarity score (0.0-1.0) between two strings.
-- Much cruder than Jaro-Winkler/Levenshtein -- fine as a quick first pass,
-- but prefer JaroWinklerDistance.sql for real dedup/match-merge work.
IF OBJECT_ID('dbo.CompareNames', 'FN') IS NOT NULL
    DROP FUNCTION dbo.CompareNames;
GO

CREATE FUNCTION dbo.CompareNames(@name1 VARCHAR(100), @name2 VARCHAR(100))
RETURNS FLOAT
AS
BEGIN
    DECLARE @len1 INT = LEN(@name1)
    DECLARE @len2 INT = LEN(@name2)
    DECLARE @i INT = 0, @j INT = 0, @score FLOAT = 0.0, @maxlen INT

    IF (@len1 = 0) RETURN CASE WHEN @len2 = 0 THEN 1.0 ELSE 0.0 END
    IF (@len2 = 0) RETURN 0.0

    SET @maxlen = CASE WHEN @len1 > @len2 THEN @len1 ELSE @len2 END

    WHILE (@i < @len1 AND @j < @len2)
    BEGIN
        IF (SUBSTRING(@name1, @i + 1, 1) = SUBSTRING(@name2, @j + 1, 1))
            SET @score = @score + 1.0
        ELSE
            SET @score = @score + 0.5
        SET @i = @i + 1
        SET @j = @j + 1
    END

    RETURN @score / @maxlen
END
GO
