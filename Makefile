TERRAFORM_DEV_DIR := infra/terraform/envs/dev
PYTHON := python3

.PHONY: test test-python test-scripts test-frontend test-terraform fmt-terraform live-dashboard

test: test-python test-scripts test-frontend test-terraform

test-python:
	$(PYTHON) -m pytest tests/unit
	$(PYTHON) -c 'from pathlib import Path; paths=[Path("dags/peakorder_paimon_pipeline.py"), Path("src/quality/validate_order_events.py"), Path("src/paimon/bootstrap_tables.py"), Path("src/paimon/load_order_events.py"), Path("src/paimon/detect_peak_pressure.py"), Path("src/serving/export_dashboard_views.py"), Path("src/ingestion/generate_peak_order_events.py"), Path("src/serving/build_frontend_sample.py"), Path("src/streaming/live_dashboard_server.py"), Path("src/streaming/publish_order_events.py")]; [compile(p.read_text(), str(p), "exec") for p in paths]; print("python compile ok")'

test-scripts:
	bash -n infra/scripts/upload_job_assets.sh
	bash -n infra/scripts/submit_emr_serverless_job.sh

test-frontend:
	$(PYTHON) -c 'import json; from pathlib import Path; data=json.loads(Path("frontend/data/dashboard.json").read_text()); assert data["summary"]["total_orders"] == 281660; assert data["summary"]["peak_orders"] == 200000; print("frontend data ok")'

fmt-terraform:
	terraform -chdir=$(TERRAFORM_DEV_DIR) fmt -recursive

test-terraform:
	terraform -chdir=$(TERRAFORM_DEV_DIR) validate

live-dashboard:
	$(PYTHON) src/streaming/live_dashboard_server.py --port 8010
