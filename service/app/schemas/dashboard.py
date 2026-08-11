from pydantic import Field

from app.schemas.common import CamelModel


class DashboardStats(CamelModel):
    pending: int = 0
    running: int = 0
    waiting_human: int = Field(0, serialization_alias="waitingHuman")
    failed: int = 0
    completed_today: int = Field(0, serialization_alias="completedToday")
    success_rate: float = Field(0.0, serialization_alias="successRate")
    online_workers: int = Field(0, serialization_alias="onlineWorkers")


class TaskTypeDistributionItem(CamelModel):
    task_type: str = Field(serialization_alias="taskType")
    count: int


class DashboardSummary(CamelModel):
    stats: DashboardStats
    task_type_distribution: list[TaskTypeDistributionItem] = Field(
        default_factory=list,
        serialization_alias="taskTypeDistribution",
    )
