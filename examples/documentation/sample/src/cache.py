"""A per-request cache for rendered fragments."""


# The key includes the locale: two locales can render the same id to different text (backlog 1).
def key(fragment_id, locale):
    return f"{locale}:{fragment_id}"


# TODO(backlog 2): evict by size, not only at the end of the request.
def new_cache():
    return {}


# Upstream wording kept verbatim (2024-06-01): "no longer retries" history-ok: quoted from the library's changelog
RETRIES = 2
