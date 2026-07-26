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
