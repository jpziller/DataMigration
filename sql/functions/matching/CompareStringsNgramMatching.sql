-- Jaccard similarity (0.0-1.0) between two strings' n-gram sets.
-- Example: SELECT dbo.CompareStringsNgramMatching(a.Name, b.Name, 3) AS Similarity
--          FROM TableA a CROSS JOIN TableB b WHERE ... > 0.8
IF OBJECT_ID('dbo.CompareStringsNgramMatching', 'FN') IS NOT NULL
    DROP FUNCTION dbo.CompareStringsNgramMatching;
GO

CREATE FUNCTION dbo.CompareStringsNgramMatching(
    @String1 VARCHAR(MAX),
    @String2 VARCHAR(MAX),
    @NgramSize INT = 3
)
RETURNS FLOAT
AS
BEGIN
    DECLARE @String1Ngrams TABLE (Ngram VARCHAR(50))
    DECLARE @String2Ngrams TABLE (Ngram VARCHAR(50))
    DECLARE @Intersection TABLE (Ngram VARCHAR(50))

    INSERT INTO @String1Ngrams
    SELECT SUBSTRING(@String1, number, @NgramSize)
    FROM master..spt_values
    WHERE type = 'P' AND number <= LEN(@String1) - (@NgramSize - 1)

    INSERT INTO @String2Ngrams
    SELECT SUBSTRING(@String2, number, @NgramSize)
    FROM master..spt_values
    WHERE type = 'P' AND number <= LEN(@String2) - (@NgramSize - 1)

    INSERT INTO @Intersection
    SELECT Ngram FROM @String1Ngrams
    WHERE Ngram IN (SELECT Ngram FROM @String2Ngrams)

    DECLARE @JaccardCoefficient FLOAT
    SELECT @JaccardCoefficient = CAST(COUNT(*) AS FLOAT) / (COUNT(DISTINCT Ngram) + COUNT(DISTINCT Ngram) - COUNT(*))
    FROM @Intersection

    RETURN @JaccardCoefficient
END
GO
