"""Entry point for the benchmark_plotting CLI.

Usage:
    python plot.py lego --base-dir results/lego --gaussian --violin
    python plot.py distance --base-dir results/distance
    python plot.py conveyor
"""

from benchmark_plotting.cli import main

if __name__ == "__main__":
    main()
