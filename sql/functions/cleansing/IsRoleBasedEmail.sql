-- Returns 1 if an email's local part is a generic role (info@, sales@, etc.)
-- rather than a named individual. Useful for flagging low-quality contact data.
IF OBJECT_ID('dbo.IsRoleBasedEmail', 'FN') IS NOT NULL
    DROP FUNCTION dbo.IsRoleBasedEmail;
GO

CREATE FUNCTION dbo.IsRoleBasedEmail(@Email VARCHAR(255))
RETURNS BIT
AS
BEGIN
    DECLARE @Result BIT = 0
    IF SUBSTRING(@Email, 1, CHARINDEX('@', @Email, 1)) IN (
        'admin@', 'administracion@', 'administration@', 'advisor@', 'all@', 'available@',
        'billing@', 'bursar@', 'busdev@', 'ceo@', 'co-op@', 'community@', 'compete@',
        'consultant@', 'contact@', 'contacto@', 'crew@', 'customercare@', 'customerservice@',
        'data@', 'design@', 'digsitesvalue@', 'director@', 'directors@', 'directory@',
        'download@', 'editor@', 'editorial@', 'editors@', 'eng@', 'enquire@', 'enquiries@',
        'enquiry@', 'everyone@', 'exec@', 'executive@', 'executives@', 'expert@', 'experts@',
        'export@', 'head.office@', 'head@', 'headoffice@', 'headteacher@', 'hostmaster@',
        'hr@', 'info@', 'information@', 'informativo@', 'investorrelations@', 'jobs@',
        'marketing@', 'master@', 'media@', 'office@', 'officeadmin@', 'operations@', 'prime@',
        'principal@', 'reception@', 'recruit@', 'recruiting@', 'request@', 'sales@', 'school@',
        'schooloffice@', 'secretary@', 'security@', 'theoffice@', 'usenet@', 'users@'
    )
        SET @Result = 1

    RETURN @Result
END
GO
