# Sleep request event time

The initial Java bridge supplied the current uptime after storage preparation. That could make an old sleep event look newer than a wake that occurred while storage work was pending. The bridge now records uptime when it first accepts a distinct sleep state and carries that timestamp through preparation to PowerManager.goToSleep.

Repeated identical sleep callbacks do not refresh that timestamp. Wake followed by a new sleep creates a new generation, obtains a new acknowledgement, and uses the newer observed event time. The coordinator receives a monotonic nonblocking uptime supplier; the Android adapter supplies SystemClock.uptimeMillis. Negative supplied timestamps are rejected before state changes.

## Pinned Android behavior

The official frameworks/base files at revision `94b4c163b7dfe5ce3607f7bb8456f9573f7de57d` establish:

- PowerManager's sleep API documents an uptime timestamp for the input event that caused the request. Its single-argument wrapper uses the application reason with zero flags.
- PowerManagerService rejects a future event time, enforces DEVICE_POWER and forwards the event time through its group transitions.
- PowerGroup's normal sleep/doze paths reject timestamps strictly earlier than the group's last wake.
- A configured wake-up delegate can handle the request before those normal group paths. The normal guards therefore are not a universal statement about every downstream power implementation.

`scripts/inspect_power_event_order.py` verifies the three complete source fingerprints and these reviewed source anchors. [The report](../evidence/power-event-order.json) records observations and limitations. This is source inspection, not execution of the real power service.

## Validation

The actual manager sources pass 21 coordinator and 20 Android-adapter host scenarios. New tests advance the clock during preparation and verify that the original event time is still forwarded; duplicate sleep events retain the old time, and wake/new-sleep uses the newer time with fresh preparation. These run against fake power/storage ports and test-only Android API shapes.

```sh
python3 scripts/inspect_power_event_order.py \
  --source-root work/framework17 --report evidence/power-event-order.json
make test-manager
```

## Remaining race

This improves event ordering but does not make the last state check atomic with the PowerManager call. Receipt time is only an observation of a CarPower callback or startup read; the original hardware event time is not recovered. CarPower wake need not update Android's last-wake time. Equal millisecond timestamps are not rejected by these strict less-than guards alone, and delegates can take another path.

A sleep call returning normally remains REQUESTED, not proof of suspend or acceptance. Real manager/power ownership, callback ordering, timestamp semantics and platform behavior need Android-level integration and validation. No actual storage, power or device operation occurred.
