import datetime
import logging
import threading
from typing import Dict, List, Tuple, Optional, Any
from urllib.parse import urlparse

from Tools.DateTimeUtility import ensure_timezone_aware

try:
    import pytz
except ImportError:
    pytz = None

try:
    from tzlocal import get_localzone_name
except ImportError:
    get_localzone_name = None

logger = logging.getLogger(__name__)


class IntelligenceSubmissionStatisticsEngine:
    """
    In-memory source submission statistics engine.

    Tracks intelligence submission counts by source domain and time granularity
    (hour/day/week/month), and records the latest submission info per source
    (title, UUID, timestamp, original URL).

    Data is kept in memory and cleared on service restart. For persistence,
    inject an external storage implementation.
    """

    GRANULARITIES = ['hour', 'day', 'week', 'month']

    def __init__(self):
        self.__lock = threading.RLock()
        self.__local_timezone = self.__detect_local_timezone()

        # (granularity, slot, source) -> {
        #   'count': int,
        #   'last_submit_time': str ISO,
        #   'last_title': str,
        #   'last_uuid': str,
        #   'last_informant': str,
        #   'updated_at': str ISO
        # }
        self.__stats: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        # source -> latest submission info
        self.__last_submissions: Dict[str, Dict[str, Any]] = {}

    # ----------------------------------------------------- Setup -----------------------------------------------------

    @staticmethod
    def __detect_local_timezone() -> str:
        try:
            if get_localzone_name:
                return get_localzone_name()
        except Exception as e:
            logger.warning(f"Could not determine local timezone: {e}")
        return "UTC"

    # ------------------------------------------------ Public API ----------------------------------------------------

    def record_submission(self,
                          informant: str,
                          title: str,
                          uuid: str,
                          submit_time: datetime.datetime):
        """
        Record a single intelligence submission.

        :param informant: Original source URL (usually CollectedData.informant)
        :param title: Intelligence title
        :param uuid: Intelligence UUID
        :param submit_time: Submission timestamp (timezone-aware recommended)
        """
        try:
            source = self._extract_source(informant)
            if not source:
                source = 'unknown'

            aware_time = ensure_timezone_aware(submit_time) if submit_time else ensure_timezone_aware(datetime.datetime.now(datetime.timezone.utc))
            local_dt = self.__to_local_time(aware_time)
            slots = self.__compute_slots(local_dt)

            time_iso = aware_time.isoformat()
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            payload = {
                'last_submit_time': time_iso,
                'last_title': title,
                'last_uuid': uuid,
                'last_informant': informant,
            }

            with self.__lock:
                for granularity, slot in slots:
                    key = (granularity, slot, source)
                    existing = self.__stats.get(key)
                    if existing is None:
                        self.__stats[key] = {
                            'count': 1,
                            **payload,
                            'updated_at': now_iso,
                        }
                    else:
                        existing['count'] += 1
                        if existing.get('last_submit_time') is None or time_iso > existing['last_submit_time']:
                            existing.update(payload)
                            existing['updated_at'] = now_iso

                last = self.__last_submissions.get(source)
                if last is None or last.get('last_submit_time') is None or time_iso > last['last_submit_time']:
                    self.__last_submissions[source] = {
                        **payload,
                        'updated_at': now_iso,
                    }
        except Exception as e:
            logger.error(f"Record submission stat failed: {e}", exc_info=True)

    def query_source_submissions(self,
                                 start_time: datetime.datetime,
                                 end_time: datetime.datetime,
                                 granularity: str = 'day',
                                 top_n: int = 20) -> Dict[str, Any]:
        """
        Query submission statistics per source for a given time range
        (time series + aggregated totals).

        :param start_time: Range start
        :param end_time: Range end
        :param granularity: hour/day/week/month
        :param top_n: Return top N sources; remaining sources are grouped as "Others"
        :return: {
            "granularity": str,
            "time_range": {"start": str, "end": str},
            "slots": [str, ...],
            "sources": [str, ...],
            "series": {source: [count, ...], ...},
            "totals": {source: total_count, ...},
            "top_sources": [{"source": str, "count": int, ...}, ...]
        }
        """
        if granularity not in self.GRANULARITIES:
            raise ValueError(f"Invalid granularity: {granularity}. Must be one of {self.GRANULARITIES}")

        start_aware = ensure_timezone_aware(start_time)
        end_aware = ensure_timezone_aware(end_time)
        start_local = self.__to_local_time(start_aware)
        end_local = self.__to_local_time(end_aware)

        slots = self.__generate_slot_range(start_local, end_local, granularity)
        if not slots:
            return self.__empty_result(granularity, start_aware, end_aware)

        try:
            with self.__lock:
                totals: Dict[str, int] = {}
                detail: Dict[str, Dict[str, Dict[str, Any]]] = {}

                for key, value in self.__stats.items():
                    g, slot, source = key
                    if g != granularity or slot < slots[0] or slot > slots[-1]:
                        continue

                    count = value.get('count', 0)
                    totals[source] = totals.get(source, 0) + count
                    if source not in detail:
                        detail[source] = {}
                    detail[source][slot] = {
                        'count': count,
                        'last_submit_time': value.get('last_submit_time'),
                        'last_title': value.get('last_title'),
                        'last_uuid': value.get('last_uuid'),
                        'last_informant': value.get('last_informant'),
                    }

                if not totals:
                    return self.__empty_result(granularity, start_aware, end_aware)

                sorted_sources = sorted(totals.items(), key=lambda x: x[1], reverse=True)
                top_sources = [s for s, _ in sorted_sources[:top_n]]
                other_sources = [s for s, _ in sorted_sources[top_n:]]

                series = {}
                for source in top_sources:
                    series[source] = [detail[source].get(slot, {'count': 0})['count'] for slot in slots]

                if other_sources:
                    series['Others'] = []
                    for slot in slots:
                        other_count = sum(
                            detail[s].get(slot, {'count': 0})['count']
                            for s in other_sources
                        )
                        series['Others'].append(other_count)
                    totals['Others'] = sum(totals[s] for s in other_sources)

                top_source_list = []
                for source, count in sorted_sources[:top_n]:
                    last_info = self.__find_latest_in_range(detail.get(source, {}))
                    top_source_list.append({
                        'source': source,
                        'count': count,
                        'last_submit_time': last_info.get('last_submit_time'),
                        'last_title': last_info.get('last_title'),
                        'last_uuid': last_info.get('last_uuid'),
                        'last_informant': last_info.get('last_informant'),
                    })

                return {
                    'granularity': granularity,
                    'time_range': {
                        'start': start_aware.isoformat(),
                        'end': end_aware.isoformat(),
                    },
                    'slots': slots,
                    'sources': list(series.keys()),
                    'series': series,
                    'totals': {k: totals[k] for k in list(series.keys())},
                    'top_sources': top_source_list,
                }
        except Exception as e:
            logger.error(f"Query source submissions failed: {e}", exc_info=True)
            return self.__empty_result(granularity, start_aware, end_aware)

    def query_last_submissions(self, limit: int = 100) -> Dict[str, Any]:
        """
        Query the latest submission info for each source.

        :param limit: Maximum number of sources to return
        :return: {
            "total_sources": int,
            "sources": [{"source": str, "last_submit_time": str, ...}]
        }
        """
        try:
            with self.__lock:
                sorted_items = sorted(
                    self.__last_submissions.items(),
                    key=lambda x: x[1].get('last_submit_time') or '',
                    reverse=True
                )
                sources = []
                for source, info in sorted_items[:limit]:
                    sources.append({
                        'source': source,
                        'last_submit_time': info.get('last_submit_time'),
                        'last_title': info.get('last_title'),
                        'last_uuid': info.get('last_uuid'),
                        'last_informant': info.get('last_informant'),
                    })

                return {
                    'total_sources': len(self.__last_submissions),
                    'sources': sources,
                }
        except Exception as e:
            logger.error(f"Query last submissions failed: {e}", exc_info=True)
            return {'total_sources': 0, 'sources': []}

    # --------------------------------------------------- Helpers ----------------------------------------------------

    @staticmethod
    def _extract_source(informant: str) -> str:
        """Extract source domain from the informant URL (strip protocol and www prefix)."""
        if not informant:
            return ''
        try:
            parsed = urlparse(informant.strip())
            netloc = parsed.netloc
            if not netloc:
                parts = informant.split('/')
                netloc = parts[0]
            netloc = netloc.split(':')[0]
            if netloc.lower().startswith('www.'):
                netloc = netloc[4:]
            return netloc.strip().lower()
        except Exception as e:
            logger.warning(f"Extract source from informant failed [{informant}]: {e}")
            return ''

    def __to_local_time(self, dt: datetime.datetime) -> datetime.datetime:
        if pytz is None:
            return dt
        try:
            local_tz = pytz.timezone(self.__local_timezone)
            return dt.astimezone(local_tz)
        except Exception as e:
            logger.warning(f"Convert to local time failed: {e}")
            return dt

    @staticmethod
    def __compute_slots(local_dt: datetime.datetime) -> List[Tuple[str, str]]:
        """Compute time slots for all granularities from a local datetime."""
        year = local_dt.year
        month = local_dt.month
        day = local_dt.day
        hour = local_dt.hour
        iso_year, iso_week, _ = local_dt.isocalendar()

        return [
            ('hour', f"{year:04d}-{month:02d}-{day:02d} {hour:02d}"),
            ('day', f"{year:04d}-{month:02d}-{day:02d}"),
            ('week', f"{iso_year:04d}-W{iso_week:02d}"),
            ('month', f"{year:04d}-{month:02d}"),
        ]

    def __generate_slot_range(self,
                              start_local: datetime.datetime,
                              end_local: datetime.datetime,
                              granularity: str) -> List[str]:
        """Generate all time-slot strings of the given granularity between start and end."""
        slots = []

        if granularity == 'hour':
            current = start_local.replace(minute=0, second=0, microsecond=0)
            end = end_local.replace(minute=0, second=0, microsecond=0)
            while current <= end:
                slots.append(current.strftime('%Y-%m-%d %H'))
                current += datetime.timedelta(hours=1)
        elif granularity == 'day':
            current = start_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end_local.replace(hour=0, minute=0, second=0, microsecond=0)
            while current <= end:
                slots.append(current.strftime('%Y-%m-%d'))
                current += datetime.timedelta(days=1)
        elif granularity == 'week':
            current = start_local - datetime.timedelta(days=start_local.weekday())
            current = current.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end_local - datetime.timedelta(days=end_local.weekday())
            end = end.replace(hour=0, minute=0, second=0, microsecond=0)
            while current <= end:
                iso_year, iso_week, _ = current.isocalendar()
                slots.append(f"{iso_year:04d}-W{iso_week:02d}")
                current += datetime.timedelta(weeks=1)
        elif granularity == 'month':
            current = start_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = end_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            while current <= end:
                slots.append(current.strftime('%Y-%m'))
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        return slots

    @staticmethod
    def __find_latest_in_range(slot_detail: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Find the latest submission among multiple slot details for one source."""
        latest = {}
        latest_time = None
        for slot, info in slot_detail.items():
            t = info.get('last_submit_time')
            if t and (latest_time is None or t > latest_time):
                latest_time = t
                latest = info
        return latest

    @staticmethod
    def __empty_result(granularity: str,
                       start_time: datetime.datetime,
                       end_time: datetime.datetime) -> Dict[str, Any]:
        return {
            'granularity': granularity,
            'time_range': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
            },
            'slots': [],
            'sources': [],
            'series': {},
            'totals': {},
            'top_sources': [],
        }
