from fastapi import Query
from pydantic import BaseModel


class Page[T](BaseModel):
    # from_attributes so FastAPI can (re)validate a Page[Model] returned by a service against
    # the router's Page[ReadSchema] response_model via attribute access, same as ORM items do.
    model_config = {"from_attributes": True}

    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    limit: int
    offset: int


def page_params(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)) -> PageParams:
    return PageParams(limit=limit, offset=offset)
