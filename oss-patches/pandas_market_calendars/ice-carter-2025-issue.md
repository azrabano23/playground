# ICE calendar treats 2025-01-09 (Carter day of mourning) as a holiday, but ICE Futures U.S. traded normally

Since 5.3.1.2, the `ICE` / `ICEUS` / `NYFE` calendar leaves 2025-01-09 out of `valid_days()` and `schedule()`:

```python
>>> import pandas_market_calendars as mcal
>>> mcal.get_calendar("ICE").valid_days("2025-01-06", "2025-01-10")
DatetimeIndex(['2025-01-06 00:00:00+00:00', '2025-01-07 00:00:00+00:00',
               '2025-01-08 00:00:00+00:00', '2025-01-10 00:00:00+00:00'],
              dtype='datetime64[us, UTC]', freq='C')
```

ICE Futures U.S. didn't close that day. According to its exchange notice (Dec 30, 2024), it held a moment of silence at 8:18 am NY time. FNG, IUT and IUS stopped trading at 9:30 am, and SR1, SR3, 30C and 30J stopped at 1:15 pm. The notice then says: "All other contracts will follow regular trading hours and daily settlement window times."

https://www.ice.com/publicdocs/futures_us/exchange_notices/ICE_Futures_US_ExNot2024MomentOfSilence20241230.pdf

The day stopped showing up when c965d08 added 2025-01-09 to the shared `USNationalDaysofMourning` list. `ICEExchangeCalendar.adhoc_holidays` uses that list. The same commit caused #486 for the CME calendars.
