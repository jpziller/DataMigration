-- Strips HTML tags and decodes common HTML entities (&amp; &lt; &gt; &nbsp; <br>).
IF OBJECT_ID('dbo.StripHtml', 'FN') IS NOT NULL
    DROP FUNCTION dbo.StripHtml;
GO

CREATE FUNCTION dbo.StripHtml(@Html VARCHAR(MAX))
RETURNS VARCHAR(MAX)
AS
BEGIN
    DECLARE @Start INT, @End INT, @Length INT

    -- Decode entities before stripping tags (order matters: &amp; before &lt;/&gt;
    -- since a double-encoded '&amp;lt;' should end up '<', not '&lt;').
    SET @Start = CHARINDEX('&amp;', @Html)
    WHILE @Start > 0
    BEGIN
        SET @Html = STUFF(@Html, @Start, 5, '&')
        SET @Start = CHARINDEX('&amp;', @Html)
    END

    SET @Start = CHARINDEX('&lt;', @Html)
    WHILE @Start > 0
    BEGIN
        SET @Html = STUFF(@Html, @Start, 4, '<')
        SET @Start = CHARINDEX('&lt;', @Html)
    END

    SET @Start = CHARINDEX('&gt;', @Html)
    WHILE @Start > 0
    BEGIN
        SET @Html = STUFF(@Html, @Start, 4, '>')
        SET @Start = CHARINDEX('&gt;', @Html)
    END

    SET @Start = CHARINDEX('&nbsp;', @Html)
    WHILE @Start > 0
    BEGIN
        SET @Html = STUFF(@Html, @Start, 6, ' ')
        SET @Start = CHARINDEX('&nbsp;', @Html)
    END

    -- Line breaks -> CRLF
    SET @Start = CHARINDEX('<br', @Html)
    WHILE @Start > 0
    BEGIN
        SET @End = CHARINDEX('>', @Html, @Start)
        IF @End = 0 BREAK
        SET @Html = STUFF(@Html, @Start, (@End - @Start) + 1, CHAR(13) + CHAR(10))
        SET @Start = CHARINDEX('<br', @Html)
    END

    -- Remove anything between remaining <...> tags
    SET @Start = CHARINDEX('<', @Html)
    SET @End = CHARINDEX('>', @Html, @Start)
    SET @Length = (@End - @Start) + 1
    WHILE @Start > 0 AND @End > 0 AND @Length > 0
    BEGIN
        SET @Html = STUFF(@Html, @Start, @Length, '')
        SET @Start = CHARINDEX('<', @Html)
        SET @End = CHARINDEX('>', @Html, @Start)
        SET @Length = (@End - @Start) + 1
    END

    RETURN LTRIM(RTRIM(@Html))
END
GO
