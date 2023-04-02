
from pcbasic.debug import DebugException

def crash():
    """Simulate a crash, for testing."""
    raise DebugException()
