from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List

class WorkloadType(str, Enum):
    deployment = "deployment"
    statefulset = "statefulset"
    daemonset   = "daemonset"
    job         = "job"

class Scenario(str, Enum):
    default = "default"
    idle    = "idle"

class CreateDataRequest(BaseModel):
    namespace: str = Field(..., min_length=1)
    workload_type: WorkloadType
    workload_name: str = Field(..., min_length=1)
    container_name: str = Field(..., min_length=1)
    scenario: Scenario = Field(default=Scenario.default)
    days: int = Field(default=1, ge=1, le=15)
    interval_in_secs: int = Field(default=15)
    measurement_duration_secs: int = Field(default=900)

    @field_validator("interval_in_secs")
    @classmethod
    def validate_interval(cls, v: int):
        if v not in (15, 30, 60):
            raise ValueError("interval_in_secs must be one of 15, 30, 60")
        return v

    @model_validator(mode="after")
    def validate_measurement_duration(self):
        if self.measurement_duration_secs < self.interval_in_secs:
            raise ValueError("measurement_duration_secs must be >= interval_in_secs")
        if self.measurement_duration_secs % self.interval_in_secs != 0:
            raise ValueError("measurement_duration_secs must be a multiple of interval_in_secs")
        return self

class DatasetOut(BaseModel):
    id: int
    created_at_utc: int
    namespace: str
    workload_type: WorkloadType
    workload_name: str
    container_name: str
    scenario: Scenario
    days: int
    interval_in_secs: int
    measurement_duration_secs: int

class AggregateOut(BaseModel):
    window_start_utc: int
    window_end_utc: int
    metric: str
    min_val: float
    max_val: float
    avg_val: float

class CreateResponse(BaseModel):
    dataset: DatasetOut
    num_samples: int
