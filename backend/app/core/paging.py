"""Pagination for list endpoints: `offset` and `limit` in the query, one row more fetched than asked,
and `X-Has-More: true|false` in the response so a client knows whether there is another page
without the cost of counting."""

from typing import Annotated

from fastapi import Query, Response

Offset = Annotated[int, Query(ge=0, le=10_000)]


def page[T](rows: list[T], limit: int, response: Response) -> list[T]:
    response.headers["X-Has-More"] = "true" if len(rows) > limit else "false"
    return rows[:limit]
