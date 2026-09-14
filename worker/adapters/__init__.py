"""External-system adapters: PowerPlatformAdapter, CopilotAdapter, SharePointAdapter.

Every adapter package here has a ``base.py`` (interface), a mock/local
implementation, and — where a real implementation is not yet verifiable
without corporate access — a documented placeholder. Business logic in
``worker/`` outside this package must only ever import the base interface
type, never a concrete implementation, so swapping mock for real is a
configuration change (see ``worker/config.py``).
"""
