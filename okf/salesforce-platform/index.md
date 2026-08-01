# Salesforce platform (cross-cloud) patterns

Migration knowledge that is **true across Salesforce clouds**, not tied to
one target product. Cloud-specific instances (Nonprofit Cloud, Consumer
Goods, etc.) live in their own subject areas and link back here; this is
the place for the general pattern those instances are examples of.

The point is transfer: a lesson learned the hard way on one cloud
(e.g. Nonprofit Cloud's recurring-gift schedules) is worth recognizing
*before* it bites on the next one, when the specifics differ but the shape
is the same.

# Patterns

* [Blocked by platform-managed records or state](blocked-by-platform-managed-records-or-state.md) -
  an operation (usually a delete/reset, sometimes an update) fails because
  the platform created or manages records/state your migration key doesn't
  cover -- auto-generated children with no migration key, or a
  state-lock. How to recognize it, how to look for it, and how to fix it.
* [Date-range fields (start/end) must be ordered](date-range-fields-must-be-ordered.md) -
  any object with a start/end date pair (schedule, campaign, contract,
  promotion) needs end >= start, but mock generators produce each date
  independently and can make it backwards. Same-object pairs get ordered
  at generation time; a cross-object date-in-window constraint is a
  transform-layer clamp. Enforced generically here.
* [Person Accounts -- the shadow Contact, and __pc / __pr suffixes](person-accounts-shadow-contact-and-field-suffixes.md) -
  a B2C person is ONE Account row plus a platform-managed paired "shadow"
  Contact; Contact fields are mirrored onto the Account as Person*/__pc/__pr.
  You migrate by loading the ACCOUNT (Person Account RecordTypeId) and never
  insert the Contact -- it's auto-created, PersonContactId gives its Id. You
  may need to RECOGNIZE __pc/__pr even when you never migrate into them.
