-- Escapes &, <, >, ", ' as HTML/XML entities.
IF OBJECT_ID('dbo.EscapeContentNote', 'FN') IS NOT NULL
    DROP FUNCTION dbo.EscapeContentNote;
GO

CREATE FUNCTION dbo.EscapeContentNote(@Input NVARCHAR(MAX))
RETURNS VARCHAR(MAX)
AS
BEGIN
    DECLARE @Result VARCHAR(MAX)
    SET @Result = REPLACE(@Input, '&', '&amp;')
    SET @Result = REPLACE(@Result, '<', '&lt;')
    SET @Result = REPLACE(@Result, '>', '&gt;')
    SET @Result = REPLACE(@Result, '"', '&quot;')
    SET @Result = REPLACE(@Result, '''', '&#39;')
    RETURN @Result
END
GO
