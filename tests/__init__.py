import os

# Render at a fixed width so snapshots don't depend on the terminal running the tests.
os.environ["COLUMNS"] = "100"
os.environ["LINES"] = "40"
