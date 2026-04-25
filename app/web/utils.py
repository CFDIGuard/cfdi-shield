from urllib.parse import urlencode


def web_url(path: str, **params: str) -> str:
    if not params:
        return path
    return f"{path}?{urlencode(params)}"
