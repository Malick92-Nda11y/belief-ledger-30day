from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol


class AdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class Observation:
    series_id: str
    observation_date: date
    value: Decimal


@dataclass(frozen=True)
class Snapshot:
    adapter: str
    source_url: str
    series_id: str
    observations: list[Observation]
    raw_sha256: str


class SourceAdapter(Protocol):
    name: str

    def fetch_snapshot(self, series_id: str) -> Snapshot:
        ...


def parse_decimal(value: str) -> Decimal | None:
    text = value.strip()
    if text in {"", ".", "NaN", "nan"}:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "belief-ledger-30day/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def _hash_bytes(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


class FredCsvAdapter:
    name = "FRED_DAILY"
    base_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

    def __init__(self, *, name: str | None = None):
        if name is not None:
            self.name = name

    def fetch_snapshot(self, series_id: str) -> Snapshot:
        url = self.base_url.format(series_id=series_id)
        raw = _download(url)
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        observations: list[Observation] = []
        for row in reader:
            date_key = "observation_date" if "observation_date" in row else "DATE"
            value_key = series_id if series_id in row else (reader.fieldnames or ["", ""])[1]
            value = parse_decimal(row.get(value_key, ""))
            if value is None:
                continue
            observations.append(Observation(series_id=series_id, observation_date=date.fromisoformat(row[date_key]), value=value))
        if not observations:
            raise AdapterError(f"FRED returned no numeric observations for {series_id}")
        return Snapshot(
            adapter=self.name,
            source_url=url,
            series_id=series_id,
            observations=observations,
            raw_sha256=_hash_bytes(raw),
        )


class VixDailyAdapter(FredCsvAdapter):
    def __init__(self):
        super().__init__(name="VIX_DAILY")


class EiaWtiDailyAdapter(FredCsvAdapter):
    def __init__(self):
        super().__init__(name="EIA_WTI_DAILY")


class FedTargetAdapter(FredCsvAdapter):
    def __init__(self):
        super().__init__(name="FRED_FED_TARGET")


class FredMonthlyAdapter(FredCsvAdapter):
    def __init__(self):
        super().__init__(name="FRED_MONTHLY")


class EcbFxDailyAdapter:
    name = "ECB_FX_DAILY"
    source_url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"

    def fetch_snapshot(self, series_id: str) -> Snapshot:
        raw = _download(self.source_url)
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = zf.namelist()
            if not names:
                raise AdapterError("ECB zip contained no files")
            csv_raw = zf.read(names[0])
        text = csv_raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if series_id not in (reader.fieldnames or []):
            raise AdapterError(f"ECB series not found: {series_id}")
        observations: list[Observation] = []
        for row in reader:
            value = parse_decimal(row.get(series_id, ""))
            if value is None:
                continue
            observations.append(Observation(series_id=series_id, observation_date=date.fromisoformat(row["Date"]), value=value))
        if not observations:
            raise AdapterError(f"ECB returned no numeric observations for {series_id}")
        observations.sort(key=lambda obs: obs.observation_date)
        return Snapshot(
            adapter=self.name,
            source_url=self.source_url,
            series_id=series_id,
            observations=observations,
            raw_sha256=_hash_bytes(csv_raw),
        )


def adapter_registry() -> dict[str, SourceAdapter]:
    return {
        "FRED_DAILY": FredCsvAdapter(name="FRED_DAILY"),
        "FRED_MONTHLY": FredMonthlyAdapter(),
        "VIX_DAILY": VixDailyAdapter(),
        "ECB_FX_DAILY": EcbFxDailyAdapter(),
        "EIA_WTI_DAILY": EiaWtiDailyAdapter(),
        "FRED_FED_TARGET": FedTargetAdapter(),
    }


def snapshot_to_json(snapshot: Snapshot) -> dict:
    return {
        "adapter": snapshot.adapter,
        "source_url": snapshot.source_url,
        "series_id": snapshot.series_id,
        "raw_sha256": snapshot.raw_sha256,
        "observations": [
            {
                "series_id": obs.series_id,
                "observation_date": obs.observation_date.isoformat(),
                "value": str(obs.value),
            }
            for obs in snapshot.observations
        ],
    }


def snapshot_from_json(raw: dict) -> Snapshot:
    return Snapshot(
        adapter=raw["adapter"],
        source_url=raw["source_url"],
        series_id=raw["series_id"],
        raw_sha256=raw["raw_sha256"],
        observations=[
            Observation(
                series_id=row["series_id"],
                observation_date=date.fromisoformat(row["observation_date"]),
                value=Decimal(str(row["value"])),
            )
            for row in raw["observations"]
        ],
    )
