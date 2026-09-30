# UNITED_STATES calendar marks Monday 3 January as a holiday

When 1 January falls on a Saturday, `Calendar(CalendarTypes.UNITED_STATES)` treats both Friday 31 December and Monday 3 January as holidays:

```python
from financepy.utils import Date, Calendar, CalendarTypes
us = Calendar(CalendarTypes.UNITED_STATES)
print(us.is_holiday(Date(31, 12, 2021)), us.is_holiday(Date(3, 1, 2022)))  # True True
```

In the US a Saturday holiday is observed on the preceding Friday, so 3 January 2022 (and likewise 3 Jan 2000, 2005, 2011, 2028) should be a business day. The `d == 3 and weekday == MON` rule in `holiday_united_states` looks like it was copied from the UK calendar. QuantLib's `UnitedStates(Settlement)` and the other US calendars in FinancePy treat these dates as business days.
