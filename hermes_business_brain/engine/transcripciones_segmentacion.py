"""Pure UTF-8 byte partitioning. Context overlap never counts as examined core."""
from bisect import bisect_left, bisect_right

from .transcripciones_modelo import ModelError, sha256_bytes, utc_now, validate_record

SEGMENTER_VERSION = "utf8-bytes-1"


def boundaries(data):
    try:
        text = data.decode("utf-8")
    except (UnicodeDecodeError, AttributeError) as exc:
        raise ModelError("UNSUPPORTED_ENCODING") from exc
    points = [0]
    for char in text:
        points.append(points[-1] + len(char.encode("utf-8")))
    return points


def segment_text(data, tr_id, version_id, *, max_core_bytes=4096, context_bytes=256):
    if not data:
        raise ModelError("INPUT_EMPTY")
    if type(max_core_bytes) is not int or max_core_bytes < 4 or type(context_bytes) is not int or context_bytes < 0:
        raise ModelError("SEGMENT_POLICY_INVALID")
    points = boundaries(data)
    digest, start, records = sha256_bytes(data), 0, []
    created = utc_now()
    while start < len(data):
        end = points[bisect_right(points, start + max_core_bytes) - 1]
        context_start = points[max(0, bisect_right(points, max(0, start-context_bytes))-1)]
        context_end = points[min(len(points)-1, bisect_left(points, min(len(data), end+context_bytes)))]
        identity = f"{tr_id}:{version_id}:{digest}:{SEGMENTER_VERSION}:{start}:{end}:{context_start}:{context_end}"
        records.append(dict(schema_version="segmento.v1", created_at=created, producer_version=SEGMENTER_VERSION,
                            segment_id="S-"+sha256_bytes(identity.encode())[:32], tr_id=tr_id, version_id=version_id,
                            text_sha256=digest, segmenter_version=SEGMENTER_VERSION, ordinal=len(records),
                            core_start=start, core_end=end, context_start=context_start, context_end=context_end,
                            speaker_refs=[], time_refs=[], boundary_reason="utf8-byte-budget"))
        start = end
    validate_partition(data, records)
    return records


def validate_partition(data, segments):
    points, cursor, ids = set(boundaries(data)), 0, set()
    if not data or not segments:
        raise ModelError("COVERAGE_GAP")
    identity = (segments[0]["tr_id"], segments[0]["version_id"], segments[0]["segmenter_version"])
    for ordinal, segment in enumerate(segments):
        validate_record("segmento", segment)
        if segment["segment_id"] in ids or segment["ordinal"] != ordinal:
            raise ModelError("SEGMENT_IDENTITY_INVALID")
        ids.add(segment["segment_id"])
        if (segment["tr_id"], segment["version_id"], segment["segmenter_version"]) != identity or segment["text_sha256"] != sha256_bytes(data):
            raise ModelError("SOURCE_CHANGED")
        start, end = segment["core_start"], segment["core_end"]
        left, right = segment["context_start"], segment["context_end"]
        if any(p not in points for p in (start,end,left,right)) or not left <= start < end <= right:
            raise ModelError("OFFSET_INVALID")
        if start != cursor:
            raise ModelError("COVERAGE_GAP")
        cursor = end
    if cursor != len(data):
        raise ModelError("COVERAGE_GAP")
    return {"valid": True, "total_core_bytes": cursor, "reconstructed_sha256": sha256_bytes(b"".join(data[s["core_start"]:s["core_end"]] for s in segments))}


def segment(text_ref, policy_version=SEGMENTER_VERSION):
    """Explicit in-memory reference: data bytes, tr_id and version_id."""
    if policy_version != SEGMENTER_VERSION:
        raise ModelError("SEGMENT_POLICY_INVALID")
    return segment_text(**text_ref)


verify_partition = validate_partition
