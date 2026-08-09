from math import ceil


def paginate(items: list, page: int, per_page: int = 5) -> tuple[list, int]:
    total_pages = max(1, ceil(len(items) / per_page))
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    return items[start : start + per_page], total_pages
