# Stop treating Monday 3 January as a US New Year holiday

## Problem

`Calendar(CalendarTypes.UNITED_STATES)` marks Monday 3 January as a holiday whenever New Year's Day falls on a Saturday (2000, 2005, 2011, 2022, 2028, ...):

```python
from financepy.utils import Date, Calendar, CalendarTypes, BusDayAdjustTypes
us = Calendar(CalendarTypes.UNITED_STATES)
us.is_holiday(Date(31, 12, 2021))                           # True (observed New Year)
us.is_holiday(Date(3, 1, 2022))                             # True (should be False)
us.adjust(Date(3, 1, 2022), BusDayAdjustTypes.FOLLOWING)    # 04-JAN-2022
```

Under US rules a Saturday holiday is observed on the Friday before, and the calendar already does this with its `d == 31 and weekday == FRI` rule. So in these years the calendar has an extra holiday on 3 January. No US convention (federal, SIFMA, NYSE) moves New Year's Day to 3 January.

## Root cause

`holiday_united_states` has a `m == 1 and d == 3 and weekday == MON` rule. That rule is correct for the UK, Australia and New Zealand, where a weekend holiday moves to the following Monday. It looks like it was copied from one of those calendars. The other US calendars in the file (`US_GOVERNMENT_SECURITIES`, `US_FEDERAL_RESERVE`, `NEW_YORK`) don't have this rule.

## Fix

Delete those three lines.

## Evidence

Before: 3 Jan 2022 and 3 Jan 2011 are holidays. After: both are business days, and 31 Dec 2021 is still a holiday.

I compared every weekday from 2000 to 2030 against QuantLib 1.43's `UnitedStates(Settlement)`. There were 6 mismatches before the fix (the five 3 January dates plus 18 June 2021) and 1 after. The remaining one is Juneteenth 2021, observed on Friday 18 June, which FinancePy includes and QuantLib's settlement calendar leaves out. That's a judgement call, and I didn't change it.

## Tests

- Added `test_us_new_year_on_saturday_not_moved_to_monday` in `tests/unit/test_FinCalendar.py`. It fails on master (`is_business_day(03-JAN-2022)` is False) and passes with the fix.
- `pytest tests/unit tests/regression/TestFinCalendar.py`: 1102 passed.
