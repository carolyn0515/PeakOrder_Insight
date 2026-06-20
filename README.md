# PeakOrder Insight

PeakOrder Insight is an AWS data engineering project for order-demand insight.
The project is organized around a lakehouse flow:

1. Raw events land in S3.
2. Streaming and batch jobs normalize records.
3. Apache Paimon stores the latest operational state with upsert support.
4. Athena, Glue, EMR, and serving stores expose analytics and application views.

## Repository Layout

```text
docs/        Architecture notes, decisions, and runbooks
infra/       Terraform and infrastructure scripts
src/         Data pipeline, Paimon, quality, and serving code
dags/        Airflow DAGs for orchestration
configs/     Environment-specific configuration
data/        Sample data and schemas
notebooks/   Exploration and validation notebooks
tests/       Unit and integration tests
assets/      Diagrams, screenshots, and portfolio images
```

## Continuous Integration

GitHub Actions runs Python unit tests, shell script syntax checks, Terraform
format checks, and Terraform validation on push and pull request events.

## Local Validation

Install development checks when needed:

```bash
pip install -r requirements-dev.txt
```

Run the local validation suite:

```bash
make test
```

Use narrower targets while iterating:

```bash
make test-python
make test-scripts
make test-terraform
```

## Core Design Position

S3 is the raw source of truth. Apache Paimon is the mutable lakehouse state layer
for fresh order, inventory, and demand tables. Serving systems such as OpenSearch,
RDS, or DynamoDB should receive only the query-optimized projections needed by
the application.
