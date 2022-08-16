from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import Any
from typing import AnyStr
from typing import Generic
from typing import Iterable
from typing import TypeVar

import pydantic
import ulid
from humps import camel
from pydantic import BaseConfig
from pydantic import BaseModel
from pydantic import Field
from pydantic import NonNegativeInt
from pydantic import StrictStr
from pydantic import conint
from pydantic import constr
from pydantic.generics import GenericModel

from . import utils


class HatConfig(BaseConfig):
    allow_population_by_field_name = True
    use_enum_values = True
    json_dumps = utils.dumps
    json_loads = utils.loads
    underscore_attrs_are_private = True


class ApiConfig(HatConfig):
    alias_generator = camel.case
    allow_mutation = False


class BaseHatModel(BaseModel, ABC):
    endpoint: StrictStr | None
    record_id: StrictStr | None

    Config = HatConfig


class BaseApiModel(BaseModel, ABC):
    Config = ApiConfig

    def dict(self, by_alias: bool = True, **kwargs) -> dict[str, Any]:
        return super().dict(by_alias=by_alias, **kwargs)

    def json(self, by_alias: bool = True, **kwargs) -> str | None:
        return super().json(by_alias=by_alias, **kwargs)


class HatModel(BaseHatModel):
    uid: str = Field(default_factory=lambda: str(ulid.ULID()))

    class Config:
        extra = pydantic.Extra.allow
        arbitrary_types_allowed = True


M = TypeVar("M", bound=HatModel)


class HatRecord(BaseApiModel, BaseHatModel, GenericModel, Generic[M]):
    data: dict[str, Any] = {}

    @classmethod
    def parse(cls, records: AnyStr, mtypes: Iterable[type[M]]) -> list[M]:
        records = cls.__config__.json_loads(records)
        if not isinstance(records, list):
            records = [records]
        # When more records exist than model types, try binding to the last one.
        mtypes, mtype = iter(mtypes), None
        models = []
        for record in records:
            mtype = next(mtypes, mtype)
            models.append(cls._to_model(record, mtype))
        return models

    @classmethod
    def _to_model(cls, record: dict[str, Any], mtype: type[M]) -> M:
        if isinstance(record["data"], (bytes, str)):
            record["data"] = cls.__config__.json_loads(record["data"])
        record = cls(**record)
        model = mtype.parse_obj(record.data)
        model.record_id = record.record_id
        model.endpoint = record.endpoint
        return model

    @classmethod
    def to_json(cls, models: Iterable[M], data_only: bool = False) -> str:
        records = map(cls._from_model, models)
        dump = cls.__config__.json_dumps
        if data_only:
            records = [dump(r.data) for r in records]
        else:
            records = [r.json() for r in records]
        return dump(records)

    @classmethod
    def _from_model(cls, model: M) -> HatRecord[M]:
        return cls(
            endpoint=model.endpoint,
            record_id=model.record_id,
            data=model.dict(exclude=set(BaseHatModel.__fields__)),
        )


class Ordering(str, Enum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


class GetOpts(BaseApiModel):
    order_by: constr(min_length=1) | None
    ordering: Ordering | None
    skip: NonNegativeInt | None
    take: conint(ge=0, le=1000) | None

    def dict(self, exclude_none: bool = True, **kwargs) -> dict:
        return super().dict(exclude_none=exclude_none, **kwargs)

    def json(self, exclude_none: bool = True, **kwargs) -> str | None:
        return super().json(exclude_none=exclude_none, **kwargs)
