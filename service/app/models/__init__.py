"""Import all models for Alembic metadata discovery."""

from app.models.artifact import Artifact  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.automation_task import AutomationTask  # noqa: F401
from app.models.autotask_setting import AutotaskSetting  # noqa: F401
from app.models.base import Base, BaseModel, not_deleted  # noqa: F401
from app.models.human_action import HumanAction  # noqa: F401
from app.models.portal_access_grant import PortalAccessGrant  # noqa: F401
from app.models.portal_account import PortalAccount  # noqa: F401
from app.models.rpa_component import RpaComponent  # noqa: F401
from app.models.rpa_run import RpaRun  # noqa: F401
from app.models.rpa_worker import RpaWorker  # noqa: F401
from app.models.run_event import RunEvent  # noqa: F401
from app.models.step_run import StepRun  # noqa: F401
from app.models.task_message import TaskMessage  # noqa: F401
from app.models.task_successor_job import TaskSuccessorJob  # noqa: F401
from app.models.user_cache import UserCache  # noqa: F401
from app.models.worker_lease import WorkerLease  # noqa: F401
from app.models.workflow_binding import WorkflowBinding  # noqa: F401
from app.models.workflow_template import WorkflowTemplate  # noqa: F401
from app.models.workflow_template_version import WorkflowTemplateVersion  # noqa: F401
