-- Decodes percent-encoded (URL-encoded) UTF-8 text back to normal characters.
IF OBJECT_ID('dbo.UrlDecode', 'FN') IS NOT NULL
    DROP FUNCTION dbo.UrlDecode;
GO

CREATE FUNCTION dbo.UrlDecode(@Url NVARCHAR(4000))
RETURNS NVARCHAR(4000)
AS
BEGIN
    DECLARE @Position INT, @High TINYINT, @Low TINYINT, @Pattern CHAR(21)
    DECLARE @Byte1Value INT, @SurrogateHigh INT, @SurrogateLow INT
    SELECT @Pattern = '%[%][0-9a-f][0-9a-f]%', @Position = PATINDEX(@Pattern, @Url)

    WHILE @Position > 0
    BEGIN
       SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
              @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
              @High = @High / 17 * 10 + @High % 17,
              @Low  = @Low  / 17 * 10 + @Low  % 17,
              @Byte1Value = 16 * @High + @Low
       IF @Byte1Value < 128 -- 1-byte UTF-8
          SELECT @Url = STUFF(@Url, @Position, 3, NCHAR(@Byte1Value)),
                 @Position = PATINDEX(@Pattern, @Url)
       ELSE IF @Byte1Value >= 192 AND @Byte1Value < 224 AND @Position > 0 -- 2-byte UTF-8
       BEGIN
           SELECT @Byte1Value = (@Byte1Value & (POWER(2,5) - 1)) * POWER(2,6),
                  @Url = STUFF(@Url, @Position, 3, ''),
                  @Position = PATINDEX(@Pattern, @Url)
           IF @Position > 0
              SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
                     @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
                     @High = @High / 17 * 10 + @High % 17,
                     @Low  = @Low  / 17 * 10 + @Low  % 17,
                     @Byte1Value = @Byte1Value + ((16 * @High + @Low) & (POWER(2,6) - 1)),
                     @Url = STUFF(@Url, @Position, 3, NCHAR(@Byte1Value)),
                     @Position = PATINDEX(@Pattern, @Url)
       END
       ELSE IF @Byte1Value >= 224 AND @Byte1Value < 240 AND @Position > 0 -- 3-byte UTF-8
       BEGIN
           SELECT @Byte1Value = (@Byte1Value & (POWER(2,4) - 1)) * POWER(2,12),
                  @Url = STUFF(@Url, @Position, 3, ''),
                  @Position = PATINDEX(@Pattern, @Url)
           IF @Position > 0
              SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
                     @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
                     @High = @High / 17 * 10 + @High % 17,
                     @Low  = @Low  / 17 * 10 + @Low  % 17,
                     @Byte1Value = @Byte1Value + ((16 * @High + @Low) & (POWER(2,6) - 1)) * POWER(2,6),
                     @Url = STUFF(@Url, @Position, 3, ''),
                     @Position = PATINDEX(@Pattern, @Url)
           IF @Position > 0
              SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
                     @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
                     @High = @High / 17 * 10 + @High % 17,
                     @Low  = @Low  / 17 * 10 + @Low  % 17,
                     @Byte1Value = @Byte1Value + ((16 * @High + @Low) & (POWER(2,6) - 1)),
                     @Url = STUFF(@Url, @Position, 3, NCHAR(@Byte1Value)),
                     @Position = PATINDEX(@Pattern, @Url)
       END
       ELSE IF @Byte1Value >= 240 AND @Position > 0 -- 4-byte UTF-8
       BEGIN
           SELECT @Byte1Value = (@Byte1Value & (POWER(2,3) - 1)) * POWER(2,18),
                  @Url = STUFF(@Url, @Position, 3, ''),
                  @Position = PATINDEX(@Pattern, @Url)
           IF @Position > 0
              SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
                     @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
                     @High = @High / 17 * 10 + @High % 17,
                     @Low  = @Low  / 17 * 10 + @Low  % 17,
                     @Byte1Value = @Byte1Value + ((16 * @High + @Low) & (POWER(2,6) - 1)) * POWER(2,12),
                     @Url = STUFF(@Url, @Position, 3, ''),
                     @Position = PATINDEX(@Pattern, @Url)
           IF @Position > 0
              SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
                     @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
                     @High = @High / 17 * 10 + @High % 17,
                     @Low  = @Low  / 17 * 10 + @Low  % 17,
                     @Byte1Value = @Byte1Value + ((16 * @High + @Low) & (POWER(2,6) - 1)) * POWER(2,6),
                     @Url = STUFF(@Url, @Position, 3, ''),
                     @Position = PATINDEX(@Pattern, @Url)
           IF @Position > 0
           BEGIN
              SELECT @High = ASCII(UPPER(SUBSTRING(@Url, @Position + 1, 1))) - 48,
                     @Low  = ASCII(UPPER(SUBSTRING(@Url, @Position + 2, 1))) - 48,
                     @High = @High / 17 * 10 + @High % 17,
                     @Low  = @Low  / 17 * 10 + @Low  % 17,
                     @Byte1Value = @Byte1Value + ((16 * @High + @Low) & (POWER(2,6) - 1))

              SELECT @SurrogateHigh = ((@Byte1Value - POWER(16,4)) & (POWER(2,20) - 1)) / POWER(2,10) + 13 * POWER(16,3) + 8 * POWER(16,2),
                     @SurrogateLow = ((@Byte1Value - POWER(16,4)) & (POWER(2,10) - 1)) + 13 * POWER(16,3) + 12 * POWER(16,2),
                     @Url = STUFF(@Url, @Position, 3, NCHAR(@SurrogateHigh) + NCHAR(@SurrogateLow)),
                     @Position = PATINDEX(@Pattern, @Url)
           END
       END
    END
    RETURN REPLACE(@Url, '+', ' ')
END
GO
