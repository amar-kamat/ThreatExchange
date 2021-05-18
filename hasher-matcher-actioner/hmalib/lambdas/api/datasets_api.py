# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved

import bottle
import typing as t
from dataclasses import dataclass, asdict
from hmalib.aws_secrets import AWSSecrets
from threatexchange.api import ThreatExchangeAPI
from hmalib.common.logging import get_logger
from .middleware import jsoninator, JSONifiable, DictParseable
from hmalib.common.config import HMAConfig
from hmalib.common import config as hmaconfig
from hmalib.common.fetcher_models import ThreatExchangeConfig
from hmalib.common.threatexchange_config import (
    sync_privacy_groups,
    create_privacy_group_if_not_exists,
)


@dataclass
class Dataset(JSONifiable):
    privacy_group_id: t.Union[int, str]
    privacy_group_name: str
    description: str
    fetcher_active: bool
    matcher_active: bool
    write_back: bool
    in_use: bool

    def to_json(self) -> t.Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Dataset":
        return cls(
            int(d["privacy_group_id"]),
            d["privacy_group_name"],
            d["description"],
            d["fetcher_active"],
            d["matcher_active"],
            d["write_back"],
            d["in_use"],
        )

    @classmethod
    def from_collab(cls, collab: ThreatExchangeConfig) -> "Dataset":
        return cls(
            collab.privacy_group_id,
            collab.privacy_group_name,
            collab.description,
            collab.fetcher_active,
            collab.matcher_active,
            collab.write_back,
            collab.in_use,
        )


@dataclass
class DatasetsResponse(JSONifiable):
    datasets_response: t.List[Dataset]

    def to_json(self) -> t.Dict:
        return {
            "datasets_response": [
                dataset.to_json() for dataset in self.datasets_response
            ]
        }


@dataclass
class SyncDatasetResponse(JSONifiable):
    response: str

    def to_json(self) -> t.Dict:
        return asdict(self)


@dataclass
class DeleteDatasetResponse(JSONifiable):
    response: str

    def to_json(self) -> t.Dict:
        return asdict(self)


@dataclass
class UpdateDatasetRequest(DictParseable):
    privacy_group_id: t.Union[int, str]
    fetcher_active: bool
    matcher_active: bool
    write_back: bool

    @classmethod
    def from_dict(cls, d: dict) -> "UpdateDatasetRequest":
        return cls(
            d["privacy_group_id"],
            d["fetcher_active"],
            d["matcher_active"],
            d["write_back"],
        )


@dataclass
class CreateDatasetRequest(DictParseable):
    privacy_group_id: t.Union[int, str]
    privacy_group_name: str
    description: str
    fetcher_active: bool
    matcher_active: bool
    write_back: bool

    @classmethod
    def from_dict(cls, d: dict) -> "CreateDatasetRequest":
        return cls(
            d["privacy_group_id"],
            d["privacy_group_name"],
            d["description"],
            d["fetcher_active"],
            d["matcher_active"],
            d["write_back"],
        )


@dataclass
class CreateDatasetResponse(JSONifiable):
    response: str

    def to_json(self) -> t.Dict:
        return asdict(self)


def get_datasets_api(hma_config_table: str) -> bottle.Bottle:
    # The documentation below expects prefix to be '/datasets/'
    datasets_api = bottle.Bottle()
    HMAConfig.initialize(hma_config_table)

    @datasets_api.get("/", apply=[jsoninator])
    def datasets() -> DatasetsResponse:
        """
        Returns all datasets.
        """
        collabs = ThreatExchangeConfig.get_all()
        return DatasetsResponse(
            datasets_response=[Dataset.from_collab(collab) for collab in collabs]
        )

    @datasets_api.post("/update", apply=[jsoninator(UpdateDatasetRequest)])
    def update_dataset(request: UpdateDatasetRequest) -> Dataset:
        """
        Update dataset fetcher_active, write_back and matcher_active
        """
        config = ThreatExchangeConfig.getx(str(request.privacy_group_id))
        config.fetcher_active = request.fetcher_active
        config.write_back = request.write_back
        config.matcher_active = request.matcher_active
        updated_config = hmaconfig.update_config(config).__dict__
        updated_config["privacy_group_id"] = updated_config["name"]
        return Dataset.from_dict(updated_config)

    @datasets_api.post("/create", apply=[jsoninator(CreateDatasetRequest)])
    def create_dataset(request: CreateDatasetRequest) -> CreateDatasetResponse:
        """
        Create a local dataset (defaults defined in CreateDatasetRequest)
        """
        assert isinstance(request, CreateDatasetRequest)

        create_privacy_group_if_not_exists(
            privacy_group_id=str(request.privacy_group_id),
            privacy_group_name=request.privacy_group_name,
            description=request.description,
            in_use=True,
            fetcher_active=request.fetcher_active,
            matcher_active=request.matcher_active,
            write_back=request.write_back,
        )

        return CreateDatasetResponse(
            response=f"Created dataset {request.privacy_group_id}"
        )

    @datasets_api.post("/sync", apply=[jsoninator])
    def sync_datasets() -> SyncDatasetResponse:
        """
        Fetch new collaborations from ThreatExchnage and potentially update the configs stored in AWS
        """
        sync_privacy_groups()
        return SyncDatasetResponse(response="Privacy groups are up to date")

    @datasets_api.post("/delete/<key>", apply=[jsoninator])
    def delete_dataset(key=None) -> DeleteDatasetResponse:
        """
        Delete dataset
        """
        config = ThreatExchangeConfig.getx(str(key))
        hmaconfig.delete_config(config)
        return DeleteDatasetResponse(response="The privacy group is deleted")

    return datasets_api
