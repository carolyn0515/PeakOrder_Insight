TERRAFORM_DEV_DIR := infra/terraform/envs/dev
PYTHON := python3

.PHONY: test test-python test-scripts test-terraform fmt-terraform

test: test-python test-scripts test-terraform

test-python:
	$(PYTHON) -m pytest tests/unit
	$(PYTHON) -c 'from pathlib import Path; paths=[Path("dags/peakorder_paimon_pipeline.py"), Path("src/quality/validate_order_events.py"), Path("src/paimon/bootstrap_tables.py"), Path("src/paimon/load_order_events.py"), Path("src/serving/export_dashboard_views.py")]; [compile(p.read_text(), str(p), "exec") for p in paths]; print("python compile ok")'

test-scripts:
	bash -n infra/scripts/upload_job_assets.sh
	bash -n infra/scripts/submit_emr_serverless_job.sh

fmt-terraform:
	terraform -chdir=$(TERRAFORM_DEV_DIR) fmt -recursive

test-terraform:
	terraform -chdir=$(TERRAFORM_DEV_DIR) validate
