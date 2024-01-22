import sys

if __name__ == "__main__":
    print(
        """
The 'cluster' package has been renamed to 'cluster_utils'.  Change the command to

    python3 -m cluster_utils.grid_search ...
"""
    )
    sys.exit(1)
