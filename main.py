"""
main.py — Entry point.

Keeping this thin: just import and call the CLI group.
This separation means `alarm_clock/cli.py` is independently importable
for testing without triggering CLI invocation.
"""

from alarm_clock.cli import cli

if __name__ == "__main__":
    cli()
