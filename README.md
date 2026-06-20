# PeakOrder Insight

> AWS 기반 피크 주문 스트리밍 / Lakehouse / 운영 대시보드 프로젝트  
> Peak-time order streaming, lakehouse processing, and operational dashboard on AWS

## 1. Project Overview

PeakOrder Insight는 점심과 저녁처럼 주문이 특정 시간대에 급격히 몰리는 상황을 가정하고, 이를 AWS 기반 데이터 파이프라인으로 수집, 저장, 처리, 관찰, 시각화한 프로젝트입니다.

이 프로젝트의 핵심 문제는 단순한 “주문 데이터 분석”이 아닙니다. 실제 운영에서는 하루 전체 주문량보다 **특정 시간대에 주문이 얼마나 빠르게 몰리는지**가 더 중요합니다. 피크 시간대 주문 폭증은 매장 운영, 재고 관리, 상품 기획, 고객 경험, 인프라 처리량에 직접적인 영향을 줍니다.

PeakOrder Insight는 이러한 피크 주문 상황을 간이 부하 테스트 형태로 재현하고, AWS 서비스들을 이용해 다음 흐름을 구성했습니다.

- Peak-shaped order event 생성
- Kinesis 기반 실시간 ingestion
- S3 raw data lake 저장
- EMR Serverless Spark 기반 처리
- Apache Paimon 기반 lakehouse current-state 관리
- Glue Data Catalog 기반 table metadata 관리
- CloudWatch 기반 metric/log/alarm 관찰
- PM, Data Engineer, ML Engineer, SRE, Leadership 관점의 dashboard 제공

## 2. Architecture

<img width="9992" height="4072" alt="image" src="https://github.com/user-attachments/assets/6a2effeb-894d-4d94-b90f-2a881fa9696c" />

PeakOrder Insight의 전체 구조는 크게 6개 계층으로 구성됩니다.

1. **Local / Simulation Layer**  
   Peak-shaped order event generator가 주문 이벤트를 생성합니다. 동일한 이벤트는 raw data lake 저장과 Kinesis replay에 함께 사용됩니다.

2. **Streaming Ingestion Layer**  
   Amazon Kinesis Data Streams가 피크 주문 이벤트를 수집합니다. CloudWatch를 통해 IncomingRecords, throughput, throttling, latency 관련 지표를 확인할 수 있습니다.

3. **Raw Data Lake Layer**  
   Amazon S3 Raw Bucket은 원천 주문 이벤트를 JSONL 형태로 저장합니다. Raw data는 재처리, 검증, 감사의 기준점 역할을 합니다.

4. **Private Processing Layer**  
   EMR Serverless Spark job이 private subnet 환경에서 raw event를 검증하고, Paimon table 적재, store pressure 계산, alert 생성, serving export 생성을 수행합니다.

5. **Lakehouse / Serving Storage Layer**  
   S3 Lakehouse Bucket은 Apache Paimon warehouse와 JSON/Parquet serving exports를 저장합니다. Paimon은 최신 운영 상태를 관리하고, JSON/Parquet export는 dashboard와 분석에 활용됩니다.

6. **Metadata / Observability / Dashboard Layer**  
   Glue Data Catalog는 S3 기반 table metadata를 관리하고, CloudWatch는 logs, metrics, alarm을 제공합니다. Dashboard는 이 결과를 역할별 의사결정 화면으로 보여줍니다.

## 3. Why This Project Matters

이 프로젝트는 단순히 AWS 서비스를 나열한 실습이 아니라, **피크 시간대 운영 문제를 AWS 데이터 아키텍처로 어떻게 해결할 수 있는지**를 보여주는 프로젝트입니다.

일반적인 데이터 파이프라인은 데이터를 저장하고 집계하는 데 집중합니다. 반면 PeakOrder Insight는 다음 질문에 답하는 데 초점을 둡니다.

- 주문이 특정 시간대에 몰릴 때 ingestion layer가 이를 감지할 수 있는가?
- 피크 시간대와 비피크 시간대의 처리 지연 차이를 관찰할 수 있는가?
- raw event를 보존하면서도 최신 운영 상태를 빠르게 반영할 수 있는가?
- PM, SRE, Data Engineer가 서로 다른 관점에서 같은 데이터를 해석할 수 있는가?
- AWS console, metric, log, table metadata, dashboard로 실행 근거를 남길 수 있는가?

즉, 이 프로젝트는 **데이터 생성 → 실시간 수집 → lakehouse 처리 → 운영 관찰 → dashboard serving**까지 하나의 흐름으로 연결한 end-to-end AWS data engineering case study입니다.

## 4. Key Technical Highlights

### 4.1 Peak-shaped Order Event Generator

이 프로젝트는 균등한 테스트 데이터를 사용하지 않았습니다. 실제 주문 서비스에서는 주문이 하루 종일 고르게 들어오지 않고, 점심과 저녁 시간대에 집중됩니다.

이를 재현하기 위해 peak-shaped order event generator를 구현했습니다.

트래픽 패턴은 다음과 같이 설계했습니다.

- 새벽/야간: 낮은 baseline traffic
- 오전/오후 일반 시간대: normal traffic
- 피크 직전/직후: ramp-up / ramp-down traffic
- 점심/저녁 피크: 집중적인 burst traffic

총 281,660건의 주문 이벤트 중 200,000건이 피크 시간대에 집중되도록 구성했습니다. 이를 통해 단순한 데이터 양이 아니라 **시간대별 주문 집중도**를 실험할 수 있도록 했습니다.

### 4.2 Time-compressed Replay for Lightweight Load Testing

실제 대규모 production traffic을 그대로 재현하려면 훨씬 많은 데이터와 긴 실행 시간이 필요합니다. 하지만 수업 및 포트폴리오 프로젝트에서는 비용, 권한, 실행 시간의 제약이 있습니다.

따라서 이 프로젝트는 event-time 기준 1시간을 wall-clock 30초로 압축하여 replay했습니다.

즉, 실제 24시간짜리 업무일을 훨씬 짧은 시간 안에 압축해서 흘려보내는 방식입니다. 이 방식은 production SLA를 증명하기 위한 것은 아니지만, 제한된 환경에서 피크형 ingestion pressure를 관찰하기에 적합합니다.

이 실험에서 중요한 기준은 총 데이터 건수가 아니라 다음 지표입니다.

- records/sec
- IncomingRecords
- IncomingBytes
- PutRecords latency
- throttled records
- failed records after retry
- consumer latency
- p95 / p99 latency
- peak vs non-peak latency comparison

### 4.3 Kinesis-based Streaming Ingestion

Kinesis Data Streams는 피크 주문 이벤트를 수집하고, CloudWatch metric을 통해 ingestion 상태를 관찰하는 역할을 합니다.

이 프로젝트에서 Kinesis를 사용한 이유는 단순 queue 처리보다 stream workload에 더 적합하기 때문입니다.

Kinesis를 통해 다음을 확인할 수 있었습니다.

- 피크 시간대 IncomingRecords 증가
- PutRecords 기반 replay 성공 여부
- throughput exceeded / throttling 발생 여부
- retry/backoff 적용 후 최종 failed record 여부
- consumer가 읽은 record 기준 latency

이를 통해 “실시간 구조를 사용했다”는 주장에 그치지 않고, 실제 AWS metric을 기반으로 streaming layer가 어떻게 동작했는지 확인했습니다.

### 4.4 S3-based Raw Data Lake

S3 Raw Bucket은 원천 주문 이벤트의 기준 저장소입니다.

Raw data를 따로 보존한 이유는 다음과 같습니다.

- 처리 로직이 바뀌어도 원천 이벤트를 다시 처리할 수 있음
- 분석 결과가 잘못되었을 때 raw event 기준으로 검증 가능
- replay, backfill, audit의 기준점 역할 수행
- serving table과 raw data를 분리해 데이터 계층을 명확하게 관리

이 구조는 단순히 dashboard용 데이터만 만드는 방식보다 데이터 엔지니어링 관점에서 더 안정적입니다.

### 4.5 EMR Serverless Spark Processing

EMR Serverless는 Spark 처리 계층으로 사용했습니다.

이 프로젝트에서는 EMR Serverless job을 통해 다음 작업을 수행했습니다.

- raw order event validation
- Paimon table bootstrap
- order event loading
- store-hour pressure 계산
- peak order alert 생성
- product demand aggregation
- JSON / Parquet serving export 생성

EMR Serverless를 사용한 이유는 Spark cluster를 직접 운영하지 않으면서도 AWS managed 환경에서 대용량 처리 구조를 보여줄 수 있기 때문입니다.

또한 VPC, IAM, S3, Glue, CloudWatch Logs와 연결되기 때문에 단순 로컬 pandas script보다 cloud computing 프로젝트로서의 의미가 큽니다.

### 4.6 Apache Paimon as Lakehouse State Layer

Apache Paimon은 S3 위에서 최신 운영 상태를 관리하는 lakehouse table format으로 사용했습니다.

단순 Parquet 파일은 append-only 분석에는 적합하지만, 최신 상태를 계속 갱신해야 하는 current-state table에는 한계가 있습니다. 예를 들어 store pressure, alert state, latest order 상태처럼 변경 가능성이 있는 데이터는 table state 관리가 필요합니다.

Paimon은 snapshot, manifest, data file, compaction 등을 통해 S3 위에서도 table-like state를 관리할 수 있습니다. 특히 primary-key table에서는 변경 데이터를 효율적으로 관리할 수 있어, 운영성 current table에 적합합니다.

이 프로젝트에서 Paimon은 raw event archive와 dashboard serving output 사이의 lakehouse state layer 역할을 합니다.

### 4.7 Glue Data Catalog for Metadata Management

Glue Data Catalog는 S3에 저장된 raw data와 serving export를 table metadata로 관리합니다.

Glue를 통해 다음을 관리했습니다.

- raw JSON table schema
- Parquet serving table schema
- S3 location
- table classification
- database structure

이를 통해 S3 파일이 단순 object 목록이 아니라 AWS 분석 서비스에서 이해 가능한 table로 정리됩니다.

### 4.8 CloudWatch-based Observability

CloudWatch는 이 프로젝트의 운영 관찰성 계층입니다.

CloudWatch를 통해 다음을 확인했습니다.

- Kinesis IncomingRecords
- Kinesis IncomingBytes
- PutRecords latency
- throttled records
- peak ingestion alarm
- EMR Serverless logs
- pipeline log groups

이 프로젝트는 결과 데이터만 만든 것이 아니라, AWS 환경에서 실제로 어떤 metric과 log가 남았는지 확인했다는 점에서 의미가 있습니다.

## 5. Load Test and Validation Summary

이 프로젝트의 간이 부하 테스트는 peak-shaped replay 방식으로 진행했습니다.

실험 조건은 다음과 같습니다.

```bash
python3 src/streaming/publish_order_events.py \
  --stream-name peakorder-insight-dev-order-events \
  --region ap-northeast-2 \
  --batch-size 250 \
  --mode peak-shaped \
  --simulated-hour-seconds 30 \
  --limit 281660 \
  --max-retries 10 \
  --retry-base-ms 500 \
  --progress-csv src/outputs/aws/kinesis_publish_peak_replay_latest.csv
```

실험의 핵심은 다음과 같습니다.

- 총 281,660건의 주문 이벤트 replay
- 피크 시간대 주문 200,000건 집중
- event-time 1시간을 wall-clock 30초로 압축
- producer retry/backoff 적용
- Kinesis metric과 latency observer로 결과 확인

관찰 결과, 피크 시간대에는 Kinesis IncomingRecords가 명확하게 증가했고, 일부 throttling/throughput pressure가 관찰되었습니다. 그러나 retry/backoff 적용 후 최종 failed records는 0으로 종료되었습니다.

Latency 측면에서는 전체 평균 약 1.25초, peak window p95 약 2초 수준의 publish-to-read latency를 관찰했습니다. 이는 현재 실험 규모와 압축 replay 조건에서 dashboard freshness 기준을 만족하는 결과입니다.

단, 이 결과를 production-scale SLA로 해석하면 안 됩니다. 이 실험은 제한된 환경에서 피크형 부하를 재현한 baseline validation입니다. 실제 production에서는 shard 수, partition key 분포, consumer parallelism, EMR job capacity, serving layer 성능을 기준으로 별도 capacity planning이 필요합니다.

## 6. Dashboard

Dashboard는 단순 시각화 페이지가 아니라 역할별 의사결정 화면으로 구성했습니다.

주요 view는 다음과 같습니다.

- **PM**: 피크 수요, 상품 수요, 매출 영향, 매장 압력, action queue
- **Data Engineering**: raw/lakehouse 상태, table output, pipeline health
- **ML Engineering**: feature readiness, future model serving 관점
- **SRE**: ingestion pressure, latency, alarm, 운영 리스크
- **Leadership**: 피크 대응 요약과 비즈니스 영향

이 구조는 같은 데이터를 서로 다른 직무가 어떻게 다르게 해석하는지 보여줍니다.

## 7. Troubleshooting Highlights

프로젝트를 진행하면서 다음과 같은 문제를 확인하고 해결했습니다.

- Kinesis PutRecords partial failure
- Throughput exceeded / throttling metric 관찰
- EMR Serverless와 Paimon runtime dependency 연결
- Paimon DDL과 Spark SQL parser 간 compatibility issue
- S3 raw/lakehouse bucket 경로 정리
- Glue table metadata 등록
- CloudWatch Logs 기반 실행 상태 확인

특히 EMR Serverless와 Paimon을 연결하는 과정에서는 단순 코드 실행이 아니라, managed Spark runtime, external JAR, SQL dialect, S3 path, IAM permission이 함께 맞아야 한다는 점을 확인했습니다.

이 과정은 AWS managed service 환경에서 lakehouse 구성 요소를 실제로 통합하고 검증했다는 점에서 중요한 의미를 갖습니다.

## 8. Repository Layout

```text
docs/        Architecture notes, decisions, report drafts, and runbooks
infra/       Terraform modules and environment-specific infrastructure code
src/         Data generation, streaming, Paimon, quality, and serving code
dags/        Airflow DAGs for orchestration experiments
configs/     Environment-specific configuration
data/        Sample data and schemas
notebooks/   Exploration and validation notebooks
tests/       Unit and integration tests
frontend/    Static and live dashboard for peak traffic monitoring
assets/      Diagrams, screenshots, and portfolio images
```

## 9. Local Validation

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the full validation suite:

```bash
make test
```

Run narrower checks:

```bash
make test-python
make test-scripts
make test-terraform
```

## 10. Running the Dashboard

Run the static dashboard:

```bash
python3 -m http.server 8000
```

Open:

```text
http://localhost:8000/frontend/
```

Run the live replay dashboard:

```bash
make live-dashboard
```

Open:

```text
http://127.0.0.1:8010/frontend/
```

## 11. Project Meaning

PeakOrder Insight demonstrates how AWS services can be combined to solve a realistic operational data problem.

The project is meaningful because it shows:

- how bursty order traffic can be simulated
- how streaming ingestion can be observed with AWS metrics
- how raw data and lakehouse state can be separated
- how serverless Spark processing can transform raw events into operational tables
- how metadata, logs, alarms, and dashboard views support system validation
- how limited-scale experiments can still provide meaningful engineering evidence when interpreted correctly

This project should not be interpreted as a full production benchmark. Instead, it is a structured AWS data engineering experiment that demonstrates the design logic, operational trade-offs, and validation process required for a peak-demand data platform.

---

# English Summary

PeakOrder Insight is an AWS data engineering project that simulates peak-time order bursts and builds an end-to-end pipeline for streaming ingestion, raw data storage, lakehouse processing, observability, and dashboard serving.

The project focuses on the fact that operational risk is driven not only by total order volume, but by how concentrated orders become during short peak windows.

The system uses:

- Amazon Kinesis for streaming ingestion
- Amazon S3 for raw and lakehouse storage
- EMR Serverless Spark for processing
- Apache Paimon for mutable lakehouse state
- AWS Glue Data Catalog for metadata
- CloudWatch for metrics, logs, and alarms
- Terraform for infrastructure as code
- A role-based dashboard for operational insight

A peak-shaped replay test was used to compress simulated event time and create visible ingestion pressure in a limited project environment. The test confirmed that peak traffic could be observed through Kinesis and CloudWatch metrics, while latency evidence provided a baseline for dashboard freshness under the tested conditions.

PeakOrder Insight is not a production-scale benchmark. It is a cloud data engineering case study that shows how to design, validate, and explain a peak-demand data architecture on AWS.
