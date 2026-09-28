# ICE: keep 2025-01-09 as a trading day

## Problem

Since 5.3.1.2, the `ICE` calendar (`ICEUS` / `NYFE`) leaves out 2025-01-09, the National Day of Mourning for President Carter. ICE Futures U.S. didn't close that day. According to its exchange notice, FNG, IUT and IUS stopped trading at 9:30 am NY and SR1, SR3, 30C and 30J stopped at 1:15 pm. For everything else, the notice says: "All other contracts will follow regular trading hours and daily settlement window times."

Source: https://www.ice.com/publicdocs/futures_us/exchange_notices/ICE_Futures_US_ExNot2024MomentOfSilence20241230.pdf

## Root cause

c965d08 added 2025-01-09 to the shared `USNationalDaysofMourning` list. That's correct for NYSE and Cboe, which did close. `ICEExchangeCalendar.adhoc_holidays` uses the same list, so ICE lost the session too. #486 is the same regression on the CME side.

## Fix

In `ICEExchangeCalendar.adhoc_holidays`, drop 2025-01-09 from the mourning-day list and add a comment linking the notice. The shared list is unchanged.

## Before / after

```python
>>> mcal.get_calendar("ICE").valid_days("2025-01-06", "2025-01-10")
# before: 2025-01-06, 01-07, 01-08, 01-10
# after:  2025-01-06, 01-07, 01-08, 01-09, 01-10
```

New test `tests/test_ice_calendar.py::test_2025_carter_day_of_mourning_open`:
- before the fix: `1 failed, 4 passed`
- after the fix: `5 passed`

## Tests run

- `pytest tests/test_ice_calendar.py`: 5 passed
- `pytest tests`: 1490 passed (Python 3.11, pandas 3.0.6)
- `ruff check` / `ruff format --check` on the touched files: clean

Note: ICE Futures U.S. put out a similar notice for 2018-12-05 (G.H.W. Bush), where only NYSE FANG+ futures closed early. The calendar still lists that date as a holiday too (see #57). I haven't changed it here because I couldn't pull up the original ICE notice, only a broker's copy of it.
