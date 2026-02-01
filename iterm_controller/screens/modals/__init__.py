"""Modal dialogs."""

from .add_document import AddDocumentModal
from .artifact_preview import ArtifactPreviewModal, ArtifactPreviewResult
from .auto_mode_config import AutoModeConfigModal
from .delete_confirm import DeleteConfirmModal
from .dependency_chain import DependencyChainModal
from .docs_picker import DocsPickerModal
from .github_actions import GitHubActionsModal
from .help_modal import HelpModal
from .mode_command import ModeCommandModal
from .plan_conflict import PlanConflictModal
from .quit_confirm import QuitAction, QuitConfirmModal
from .rename_document import RenameDocumentModal
from .script_picker import ScriptPickerModal
from .stage_advance import StageAdvanceModal

__all__ = [
    "AddDocumentModal",
    "ArtifactPreviewModal",
    "ArtifactPreviewResult",
    "AutoModeConfigModal",
    "DeleteConfirmModal",
    "DependencyChainModal",
    "DocsPickerModal",
    "GitHubActionsModal",
    "HelpModal",
    "ModeCommandModal",
    "PlanConflictModal",
    "QuitAction",
    "QuitConfirmModal",
    "RenameDocumentModal",
    "ScriptPickerModal",
    "StageAdvanceModal",
]
