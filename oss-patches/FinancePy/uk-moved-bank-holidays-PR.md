# Fix UK calendar treating moved bank holidays as holidays

## Problem

The `UNITED_KINGDOM` and `LONDON` calendars list 8 May 2020 and 2 June 2022 as special holidays, but they still flag the original Mondays (4 May 2020 and 30 May 2022) as holidays too. The 2002 and 2012 spring bank holiday moves have the same problem, and the jubilee dates in those years and the 29 April 2011 royal wedding are missing.

```python
from financepy.utils import Date, Calendar, CalendarTypes, BusDayAdjustTypes
uk = Calendar(CalendarTypes.UNITED_KINGDOM)
uk.is_business_day(Date(30, 5, 2022))                              # False (should be True)
uk.adjust(Date(30, 5, 2022), BusDayAdjustTypes.FOLLOWING)          # 31-MAY-2022 (should be 30-MAY-2022)
```

## Root cause

`holiday_london` adds the new dates through `special_holidays`, but the generic rules for "first Monday in May" and "last Monday in May" still return True for the dates the holiday was moved away from.

## Fix

Add a small `moved_holidays` set that is checked first and returns False, and add the missing one-off dates (3–4 June 2002, 29 April 2011, 4–5 June 2012) to `special_holidays`. Nothing else changes.

## Evidence

| Date | Before | After |
|---|---|---|
| 27 May 2002, 28 May 2012, 4 May 2020, 30 May 2022 | holiday | business day |
| 3–4 Jun 2002, 29 Apr 2011, 4–5 Jun 2012 | business day | holiday |

I also compared every weekday from 2000 to 2030 against QuantLib 1.43's `UnitedKingdom(Settlement)` calendar. There were 9 mismatches before the fix and none after, for both `UNITED_KINGDOM` and `LONDON`.

## Tests

- Added `test_uk_moved_bank_holidays` in `tests/unit/test_FinCalendar.py`. It fails on master (`assert cal.is_business_day(Date(27, 5, 2002))` is False) and passes with the fix.
- `pytest tests/unit tests/regression/TestFinCalendar.py`: 1102 passed.
