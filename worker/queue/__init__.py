"""The job queue — a thin wrapper over SharePointAdapter's DocumentationJobs
access. SharePoint IS the queue (ADR-003); this module exists only to give
worker/main.py a small, queue-shaped surface to poll."""
