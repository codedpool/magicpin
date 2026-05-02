"""Pipeline package — tick loop + should_send gate + suppression hookup."""

from pipeline.tick_loop import run_tick
from pipeline.should_send import should_send

__all__ = ["run_tick", "should_send"]
