# results/ index

Every number in `report/report.pdf` comes from a file here. Files starting with `attempt1_` are the first, invalid runs
(the cluster was starved and Traefik restarted); they are kept as evidence and explained in the report (Task 4).

| Task | Files |
|---|---|
| 1 data | `clean_counts.json`, `object_storage_listing.txt`, `teacher_validation*.json*`, `teacher_val_raw/`, `ollama_version.txt` |
| 2 model | `train_v1.log`, `train_v2.log` (loss in `training/loss*.csv`), `student_v1*`, `student_v2*`, `base_pythia*`, `teacher_validation.json` |
| 3 service | `task3_50_requests.txt` (peak memory), `task3_fault_inject.txt` |
| 4 Kubernetes | `rolling_update_log.txt`, `rolling_load_*`, `recovery_log.txt`, `coldstart*.txt`, `endpoints_while_loading.txt`, `hpa_scaling.txt`, `hpa_load_*`, `loadtest_headers.json` (load balancing) |
| 5 network | `nacl_check.txt` |
| 6 reproducibility | `make_up.log`, `fresh_clone_make_up.log` (fresh clone, 18 min 55 s), `make_down.log`; CI run links are in the report |
| 7 performance | `loadtest_*` (standard command), `task7_kubectl_top.txt` |
