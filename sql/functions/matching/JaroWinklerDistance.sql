-- Jaro-Winkler string similarity (0.0-1.0, higher = more similar).
-- Useful for fuzzy-matching source vs. target records during dedup/merge.
-- Example: SELECT dbo.JaroWinklerDistance('apple', 'aple')  -> ~0.96
IF OBJECT_ID('dbo.JaroWinklerDistance', 'FN') IS NOT NULL
    DROP FUNCTION dbo.JaroWinklerDistance;
GO

CREATE FUNCTION dbo.JaroWinklerDistance(@str1 VARCHAR(100), @str2 VARCHAR(100))
RETURNS FLOAT
AS
BEGIN
    DECLARE @matches1 VARCHAR(100) = '', @matches2 VARCHAR(100) = '', @matches INT = 0
    DECLARE @transpositions INT = 0, @jaro FLOAT = 0.0, @prefix INT = 0, @scale_factor FLOAT = 0.1

    SELECT @matches1 = STUFF((SELECT '|' + SUBSTRING(@str1, number, 1)
                               FROM master..spt_values
                               WHERE type = 'P' AND number <= LEN(@str1) AND number > 0
                               ORDER BY number
                               FOR XML PATH('')), 1, 1, ''),
           @matches2 = STUFF((SELECT '|' + SUBSTRING(@str2, number, 1)
                               FROM master..spt_values
                               WHERE type = 'P' AND number <= LEN(@str2) AND number > 0
                               ORDER BY number
                               FOR XML PATH('')), 1, 1, '')

    SELECT @matches = LEN(REPLACE(@matches1, '|', '') + REPLACE(@matches2, '|', '')) - LEN(REPLACE(@matches1 + @matches2, '|', ''))

    SELECT @transpositions = (SELECT COUNT(*)
                              FROM (SELECT SUBSTRING(@matches1, number, 1) AS match1, SUBSTRING(@matches2, number, 1) AS match2
                                    FROM master..spt_values
                                    WHERE type = 'P' AND number <= LEN(@matches1) AND number > 0
                                  ) AS matches
                              WHERE match1 <> '|' AND match1 = match2)

    SELECT @jaro = CASE WHEN @matches = 0 THEN 0.0 ELSE
        ((1.0 * @matches) / (3.0 * LEN(@str1))) +
        ((1.0 * @matches) / (3.0 * LEN(@str2))) +
        ((1.0 * (@matches - @transpositions)) / (3.0 * @matches))
    END

    WHILE SUBSTRING(@str1, @prefix + 1, 1) = SUBSTRING(@str2, @prefix + 1, 1) AND @prefix < 4
        SET @prefix = @prefix + 1

    SELECT @jaro = @jaro + (@prefix * @scale_factor * (1 - @jaro))

    RETURN @jaro
END
GO
