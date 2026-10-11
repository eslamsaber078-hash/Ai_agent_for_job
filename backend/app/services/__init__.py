from .providers import (
    REGISTRY,
    ArbeitnowProvider,
    HimalayasProvider,
    JobicyProvider,
    RemoteOKProvider,
    RemotiveProvider,
    WeWorkRemotelyProvider,
    WorkingNomadsProvider,
    ensure_default_sources,
    ensure_sources,
    hide_stale_jobs,
    merge_duplicate_jobs,
    run_discovery,
)
from .matching import compute_match
from .assistant import generate_material
from .scheduler import apply_settings, get_scheduler, run_search_now, start_scheduler, stop_scheduler

__all__ = [
    "REGISTRY", "RemotiveProvider", "RemoteOKProvider", "JobicyProvider", "ArbeitnowProvider",
    "WeWorkRemotelyProvider", "HimalayasProvider", "WorkingNomadsProvider",
    "ensure_default_sources", "ensure_sources", "hide_stale_jobs", "merge_duplicate_jobs", "run_discovery",
    "compute_match", "generate_material",
    "apply_settings", "get_scheduler", "run_search_now", "start_scheduler", "stop_scheduler",
]
