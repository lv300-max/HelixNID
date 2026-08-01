#!/usr/bin/env python3
"""Normalize authorized carrier webhook/API payloads into HELIXNID tracking events.

The normalizers accept payloads already received from an authorized carrier integration.
They do not bypass authentication, scrape private tracking records, or create evidence.
"""
from __future__ import annotations

from typing import Any


def _first(payload: dict[str, Any], paths: list[tuple[str, ...]]) -> Any:
    for path in paths:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if value not in (None, "", []):
            return value
    return None


def normalize_fedex(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = _first(payload, [
        ("output", "completeTrackResults"),
        ("completeTrackResults",),
        ("trackResults",),
    ]) or []
    if isinstance(results, dict):
        results = [results]
    events: list[dict[str, Any]] = []
    for result in results:
        tracks = result.get("trackResults") if isinstance(result, dict) else None
        if tracks is None:
            tracks = [result]
        if isinstance(tracks, dict):
            tracks = [tracks]
        for track in tracks or []:
            tracking = _first(track, [("trackingNumberInfo", "trackingNumber"), ("trackingNumber",)])
            carrier_eta = _first(track, [
                ("estimatedDeliveryTimeWindow", "window", "ends"),
                ("dateAndTimes", "estimatedDelivery"),
                ("estimatedDeliveryTime",),
            ])
            scan_events = track.get("scanEvents") or []
            if not scan_events:
                scan_events = [{
                    "date": _first(track, [("latestStatusDetail", "scanLocation", "date"), ("estimatedDeliveryTime",)]),
                    "eventDescription": _first(track, [("latestStatusDetail", "description"), ("latestStatus",)]),
                    "scanLocation": _first(track, [("latestStatusDetail", "scanLocation"),]),
                }]
            for event in scan_events:
                location = event.get("scanLocation") or {}
                if isinstance(location, dict):
                    location = ", ".join(str(x) for x in [location.get("city"), location.get("stateOrProvinceCode"), location.get("countryCode")] if x)
                timestamp = event.get("date") or event.get("dateTime") or event.get("timestamp")
                status = event.get("eventDescription") or event.get("derivedStatus") or event.get("eventType") or "UNKNOWN"
                if tracking and timestamp:
                    events.append({
                        "shipment_id": str(tracking),
                        "tracking_number": str(tracking),
                        "carrier": "FedEx",
                        "event_timestamp": timestamp,
                        "status": status,
                        "location": location or None,
                        "estimated_delivery": carrier_eta,
                        "exception_code": event.get("exceptionCode") or event.get("delayDetail"),
                    })
    return events


def normalize_usps(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_events = payload.get("events") or payload.get("trackingEvents") or [payload]
    if isinstance(raw_events, dict):
        raw_events = [raw_events]
    events = []
    for event in raw_events:
        shipment_id = event.get("externalLoadNumber") or event.get("trackingNumber") or payload.get("externalLoadNumber")
        timestamp = event.get("eventTimestamp") or event.get("timestamp") or event.get("appointmentDate")
        status = event.get("status") or event.get("eventType") or event.get("milestone") or "UNKNOWN"
        location = event.get("location") or event.get("dropSiteKey") or event.get("zipCode")
        eta = event.get("estimatedArrival") or event.get("estimatedDelivery") or event.get("eta")
        if shipment_id and timestamp:
            events.append({
                "shipment_id": str(shipment_id),
                "tracking_number": str(shipment_id),
                "carrier": "USPS",
                "event_timestamp": timestamp,
                "status": status,
                "location": str(location) if location else None,
                "estimated_delivery": eta,
                "exception_code": event.get("delayReason") or event.get("exceptionCode"),
            })
    return events


def normalize_generic(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_events = payload.get("events") or payload.get("timeline") or [payload]
    if isinstance(raw_events, dict):
        raw_events = [raw_events]
    shipment_id = payload.get("shipment_id") or payload.get("tracking_number") or payload.get("trackingNumber")
    carrier = payload.get("carrier")
    eta = payload.get("estimated_delivery") or payload.get("estimatedDelivery")
    events = []
    for event in raw_events:
        sid = event.get("shipment_id") or event.get("tracking_number") or event.get("trackingNumber") or shipment_id
        timestamp = event.get("event_timestamp") or event.get("timestamp") or event.get("date")
        status = event.get("status") or event.get("description") or event.get("event") or "UNKNOWN"
        if sid and timestamp:
            events.append({
                "shipment_id": str(sid),
                "tracking_number": str(sid),
                "carrier": event.get("carrier") or carrier,
                "event_timestamp": timestamp,
                "status": status,
                "location": event.get("location"),
                "estimated_delivery": event.get("estimated_delivery") or event.get("estimatedDelivery") or eta,
                "exception_code": event.get("exception_code") or event.get("exceptionCode"),
            })
    return events


def normalize(provider: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    key = provider.strip().lower()
    if key in {"fedex", "federal_express"}:
        events = normalize_fedex(payload)
    elif key in {"usps", "postal_service"}:
        events = normalize_usps(payload)
    elif key in {"generic", "multi", "pakket"}:
        events = normalize_generic(payload)
    else:
        raise ValueError("provider must be fedex, usps, generic, or pakket")
    if not events:
        raise ValueError("no usable tracking events found in provider payload")
    return events
