#
# name:          scheduler.py
# part of:       ha-energy-optimizer
# location:      /ha-energy-optimizer/ha-energy-optimizer/scheduler/scheduler.py
# part version:  p_v0.4
# altered:       2026-07-28
#
# p_v0.4: datetime.now() -> now_local(config.location.timezone). Kritiek:
# dit bepaalt exact wanneer optimizer.run_time, evening_planning_time,
# daily_report_time en profile_update_time daadwerkelijk afgaan. Als de
# container-klok verkeerd staat (bekend HA Supervisor-probleem, zie
# config/localtime.py), vuurden deze dagelijkse taken op het verkeerde
# werkelijke moment — bijv. de avondplanning om "21:00" volgens de
# container terwijl het lokaal pas 19:00 was.
#
# p_v0.4: datetime.now() -> now_local(config.location.timezone). Critical:
# this determines exactly when optimizer.run_time, evening_planning_time,
# daily_report_time and profile_update_time actually fire. If the
# container clock is wrong (known HA Supervisor issue, see
# config/localtime.py), these daily tasks fired at the wrong real-world
# moment — e.g. the evening planning at "21:00" per the container while it
# was only 19:00 locally.
#
import asyncio
import logging
from datetime import datetime, time
from config.config import AppConfig
from config.localtime import now_local

logger = logging.getLogger(__name__)


class TaskScheduler:
    def __init__(self, config: AppConfig):
        self._config = config
        self._interval_tasks: list[tuple[int, callable]] = []
        self._daily_tasks: list[tuple[str, callable]] = []

    def every(self, seconds: int, task: callable) -> None:
        self._interval_tasks.append((seconds, task))

    def daily(self, time_str: str, task: callable) -> None:
        self._daily_tasks.append((time_str, task))

    async def run_forever(self) -> None:
        tasks = []
        for seconds, task in self._interval_tasks:
            tasks.append(self._run_interval(seconds, task))
        for time_str, task in self._daily_tasks:
            tasks.append(self._run_daily(time_str, task))
        await asyncio.gather(*tasks)

    async def _run_interval(self, seconds: int, task: callable) -> None:
        while True:
            try:
                task()
            except Exception as e:
                logger.exception(f"Intervaltaak {task.__name__} gefaald: {e}")
            await asyncio.sleep(seconds)

    async def _run_daily(self, time_str: str, task: callable) -> None:
        h, m = map(int, time_str.split(":"))
        target = time(h, m)
        tz_name = getattr(self._config.location, "timezone", "Europe/Amsterdam")
        while True:
            seconds_until = _seconds_until(now_local(tz_name), target)
            await asyncio.sleep(seconds_until)
            try:
                task()
            except Exception as e:
                logger.exception(f"Dagelijkse taak {task.__name__} gefaald: {e}")
            await asyncio.sleep(60)


def _seconds_until(now: datetime, target: time) -> float:
    target_today = now.replace(
        hour=target.hour, minute=target.minute, second=0, microsecond=0
    )
    delta = (target_today - now).total_seconds()
    if delta <= 0:
        delta += 86400
    return delta

#
