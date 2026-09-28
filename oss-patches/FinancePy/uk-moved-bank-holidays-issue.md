# UK calendar still treats moved bank holidays as holidays (e.g. 30 May 2022)

`Calendar(CalendarTypes.UNITED_KINGDOM)` (and `LONDON`) lists 8 May 2020 and 2 June 2022 as special holidays, but it still flags the original dates too:

```python
from financepy.utils import Date, Calendar, CalendarTypes
uk = Calendar(CalendarTypes.UNITED_KINGDOM)
print(uk.is_business_day(Date(4, 5, 2020)))   # False, but the holiday moved to 8 May
print(uk.is_business_day(Date(30, 5, 2022)))  # False, but the holiday moved to 2 June
```

The 2002 and 2012 spring bank holidays have the same problem (27 May 2002 and 28 May 2012 should be business days). The jubilee holidays (3–4 June 2002, 4–5 June 2012) and the 29 April 2011 royal wedding are missing. Compared with QuantLib's UK settlement calendar, there are 9 mismatches on weekdays between 2000 and 2030, and all of them are these dates.

Because of this, following/modified-following adjustment rolls payments dated on those Mondays to the next day.
