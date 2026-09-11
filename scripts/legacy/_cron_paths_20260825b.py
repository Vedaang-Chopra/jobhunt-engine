"""Print canonical data-root paths (read-only)."""
import config_lib

print(config_lib.data_root())
for k in ("people_sweep_csv", "hiring_posts_csv", "search_runs_csv"):
    try:
        print(k, config_lib.path(k))
    except Exception as e:
        print(k, "ERR", e)
