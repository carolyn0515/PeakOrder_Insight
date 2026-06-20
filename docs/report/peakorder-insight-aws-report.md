# PeakOrder Insight AWS Real-Time Lakehouse Report

## 1. Executive Summary

PeakOrder Insight는 점심과 저녁처럼 주문이 특정 시간대에 몰리는 배달/커머스 운영 상황을 가정하고, 주문 이벤트를 실시간으로 수집한 뒤 운영 의사결정에 필요한 지표로 변환하는 AWS 기반 데이터 엔지니어링 프로젝트이다.

이 프로젝트의 핵심 질문은 단순히 "주문 데이터를 저장할 수 있는가"가 아니라, 다음 세 가지이다.

1. 피크 시간대 주문 폭증을 데이터 파이프라인이 흡수할 수 있는가?
2. 수집된 이벤트가 운영자가 개입할 수 있을 만큼 빠르게 관찰되는가?
3. 원천 이벤트, 처리 결과, 운영 알림이 재현 가능한 AWS 리소스와 증거로 남는가?

구현 결과, 총 281,660건의 주문 이벤트를 Kinesis로 재생했고, 그중 200,000건은 피크 윈도우에 집중되도록 설계했다. Producer 실행 결과 전체 이벤트가 실패 없이 전송되었고, consumer latency 로그 기준 전체 평균 publish-to-read latency는 약 1.26초, p95는 약 2.03초로 측정되었다. 피크 시간대만 따로 보아도 p95는 약 2.06초 수준으로, 피크 부하에서도 실시간 운영 대시보드가 의미 있는 freshness를 유지할 수 있음을 확인했다.

데이터는 S3 raw zone에 JSONL 형태로 적재되고, EMR Serverless Spark 작업을 통해 Paimon 기반 lakehouse 상태와 dashboard export 데이터로 변환된다. Glue Data Catalog는 raw table과 serving table을 관리하며, CloudWatch는 Kinesis ingestion metric, EMR log group, peak ingestion alarm을 통해 운영 관찰성을 제공한다. 프론트엔드는 PM, Data Engineer, ML Engineer, SRE, Leadership 관점별로 같은 데이터의 의미를 다르게 해석할 수 있도록 구성했다.

## 2. Problem Definition

피크 주문 시스템의 어려움은 전체 일간 주문량보다 순간 밀도에 있다. 하루 주문량이 동일하더라도 24시간에 고르게 분산되는 경우와 12시, 13시, 18시, 19시에 몰리는 경우는 운영 난이도가 완전히 다르다. 후자의 경우 매장별 조리 capacity, 품절 가능성, 배달 지연, 고객 취소, 고객센터 문의가 동시에 증가한다.

따라서 이 프로젝트는 batch 집계만으로는 늦게 발견되는 피크 압력을 Kinesis 기반 event stream으로 먼저 관찰하고, lakehouse에 누적된 상태를 이용해 운영 지표와 PM 의사결정 지표로 연결하는 구조를 선택했다.

핵심 운영 질문은 다음과 같다.

| 질문 | 필요한 데이터 | 사용 위치 |
|---|---:|---|
| 지금 주문이 평소 대비 얼마나 몰리는가? | 시간대별 order count, store baseline | PM/SRE dashboard |
| 어떤 매장이 피크 압력을 가장 크게 받는가? | store-hour pressure ratio | PM/SRE action queue |
| 어떤 상품이 피크 수요를 주도하는가? | product demand, gross sales | PM inventory/product decision |
| 피크 이벤트가 실시간 관찰 가능한가? | Kinesis publish-to-read latency | architecture validation |
| 알림 기준이 실제 피크를 포착하는가? | IncomingRecords CloudWatch alarm | observability evidence |

## 3. Architecture Overview

> 다이어그램 삽입 위치: 사용자가 직접 작성하는 AWS architecture diagram을 여기에 배치한다.

시스템은 다음 레이어로 구성된다.

| Layer | AWS/Local Component | 역할 |
|---|---|---|
| Event generation | `publish_order_events.py` | 피크 형태의 주문 이벤트를 Kinesis로 재생 |
| Streaming ingestion | Amazon Kinesis Data Streams | 실시간 주문 이벤트 수집 |
| Raw storage | Amazon S3 raw bucket | 원천 JSONL 이벤트 보관 |
| Processing | EMR Serverless Spark | raw event 검증, Paimon 적재, serving export 생성 |
| Lakehouse state | Apache Paimon on S3 | 최신 상태 테이블과 분석 가능한 lakehouse 상태 관리 |
| Metadata catalog | AWS Glue Data Catalog | raw/export table schema와 위치 관리 |
| Serving export | S3 JSON/Parquet export | frontend dashboard와 분석용 serving data 제공 |
| Observability | CloudWatch Logs, Metrics, Alarm | ingestion, job log, peak alarm 관찰 |
| Network | VPC, private subnets, S3/Logs endpoints | private processing 환경과 AWS service 접근 제어 |
| Dashboard | Static frontend + live local server | 역할별 KPI와 운영 지표 시각화 |

이 구조의 의도는 streaming과 lakehouse를 서로 대체 관계로 보지 않는 것이다. Kinesis는 빠른 감지와 관찰을 담당하고, S3/Paimon/Glue는 재처리, 검증, 상태 관리, 보고 가능한 증거를 담당한다.

## 4. Peak Traffic Simulation Design

일반적인 샘플 데이터는 시간대별 volume 차이가 작아 real-time architecture의 필요성을 설명하기 어렵다. 이 프로젝트에서는 이벤트 시간 기준으로 점심과 저녁 시간대에 주문을 집중시켜 실제 운영에서 문제가 되는 "짧은 시간의 과밀"을 재현했다.

### 4.1 Event Volume

총 이벤트 수는 281,660건이다. 이 중 피크 시간대인 12시, 13시, 18시, 19시에 각각 50,000건씩 배치해 총 200,000건, 즉 전체의 약 71%가 피크 윈도우에 집중되도록 구성했다.

| 구간 | 시간대 | 이벤트 수 | 해석 |
|---|---|---:|---|
| Off-peak | 00-07, 22-23 | 시간당 1,666건 | 야간/비활성 시간 |
| Shoulder | 08-10, 14-16, 21 | 시간당 5,000건 | 일반 운영 시간 |
| Pre/Post peak | 11, 17, 20 | 시간당 10,000건 | 피크 전후 상승/하강 |
| Peak | 12, 13, 18, 19 | 시간당 50,000건 | 점심/저녁 주문 폭증 |

### 4.2 Replay Method

Producer는 단순히 고정 속도로 데이터를 넣지 않고 `--mode peak-shaped`로 실행했다.

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

이 실행은 24시간의 이벤트 시간을 약 14분으로 압축해 재생한다. 따라서 CloudWatch의 wall-clock 기준 ingestion graph에서도 일정한 직선이 아니라 특정 구간에서 record 수가 급증하는 형태가 나타난다.

Producer 결과 요약은 다음과 같다.

| Metric | Value |
|---|---:|
| Published records | 281,660 |
| Elapsed time | 837.493 seconds |
| Overall average publish rate | 336.31 records/sec |
| Failed records | 0 |
| Batch size | 250 |
| Retry strategy | partial PutRecords retry with exponential backoff |

피크 시간대의 실제 재생 속도는 비피크보다 훨씬 높게 나타났다.

| Event hour group | Representative publish rate |
|---|---:|
| Off-peak 01-07/23 | 약 54-58 records/sec |
| Shoulder 08-10/14-16/21 | 약 146-160 records/sec |
| Pre/Post peak 11/17/20 | 약 279-289 records/sec |
| Peak 12/13/18/19 | 약 893-1,129 records/sec |

즉, 데이터 자체뿐 아니라 Kinesis로 들어가는 ingestion rate도 피크 패턴을 갖도록 설계되었다.

## 5. Streaming and Latency Validation

### 5.1 Why Latency Evidence Matters

이 프로젝트에서 latency log는 단순한 부가 로그가 아니라 architecture justification의 핵심 증거이다. 실시간 구조를 선택했다면 "실제로 빠르게 읽을 수 있었는가"를 증명해야 한다. 특히 PM dashboard의 decision freshness, SRE의 incident detection, CloudWatch alarm의 유효성은 모두 이벤트가 너무 늦게 관찰되지 않는다는 전제 위에 있다.

Consumer는 Kinesis에서 record를 읽고, producer가 payload에 추가한 `_published_at_utc`와 consumer read time을 비교해 publish-to-read latency를 기록한다. 이는 애플리케이션 관점에서 "이벤트가 전송된 뒤 dashboard/consumer 계층에서 관찰 가능한 상태가 되기까지 걸린 시간"에 가깝다.

### 5.2 Latency Result

Latency CSV 기준 전체 281,660건이 측정되었다.

| Segment | Records | Mean latency | Median | Std. dev | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| All records | 281,660 | 1,255.55 ms | 1,251.67 ms | 452.30 ms | 2,026.83 ms | 2,221.86 ms | 2,375.61 ms |
| Peak hours | 200,000 | 1,302.02 ms | 1,300.82 ms | 451.04 ms | 2,056.72 ms | 2,248.12 ms | 2,375.61 ms |
| Shoulder hours | 65,000 | 1,147.06 ms | 1,135.04 ms | 441.58 ms | 1,906.74 ms | 2,053.13 ms | 2,264.55 ms |
| Off-peak hours | 16,660 | 1,120.98 ms | 1,108.60 ms | 406.91 ms | 1,835.60 ms | 2,062.45 ms | 2,105.13 ms |

### 5.3 Interpretation

피크 시간대 latency가 비피크보다 증가한 것은 자연스럽다. 피크 구간은 record volume이 훨씬 크고 Kinesis write throughput exceeded/throttled metric도 일부 나타났기 때문이다. 중요한 점은 증가 폭이 운영적으로 허용 가능한 범위에 머물렀다는 것이다.

전체 p95는 약 2.03초, 피크 p95는 약 2.06초로 3초 미만이다. PM dashboard의 decision rule은 "3초 미만이면 짧은 피크 윈도우 안에서 live intervention이 가능하다"는 기준을 사용한다. 이 기준에 따르면 현재 구조는 피크 상황에서도 실시간 관찰 요구사항을 충족한다.

단, 이 결과는 production SLA가 아니라 이번 프로젝트 실험 환경의 validation evidence로 해석해야 한다. 실제 운영에서는 shard 수, enhanced monitoring, consumer parallelism, retry backoff, downstream processing time을 별도로 튜닝해야 한다.

## 6. AWS Evidence Summary

### 6.1 Frontend Dashboard

캡처: `Peak demand and customer impact` PM dashboard

프론트엔드는 단순한 시각화가 아니라 역할별 의사결정 화면으로 구성했다. PM 탭은 다음 KPI를 제공한다.

| KPI | Captured value | Decision meaning |
|---|---:|---|
| Total orders | 281,660 | 실험 데이터 전체 규모 |
| Peak-window orders | 200,000 | 피크 윈도우 집중도 |
| Gross sales | ₩2,753,629,300 | 피크 대응의 사업 영향 |
| Peak alerts | 16 | store-hour intervention 후보 |
| Peak demand concentration | 71% | 피크가 비즈니스 대부분을 지배하는지 판단 |
| Store pressure ceiling | 4.34x | 특정 매장 capacity pressure |
| Decision freshness | 1,337 ms | Kinesis replay 기반 관찰 지연 |

이 화면은 데이터 엔지니어링 결과를 비즈니스 의사결정으로 연결하는 최종 serving layer이다.

### 6.2 Kinesis Data Stream

캡처: `peakorder-insight-dev-order-events` stream monitoring

Kinesis monitoring 화면에서 다음을 확인했다.

| Evidence | Meaning |
|---|---|
| Stream status: Active | ingestion layer가 정상 생성됨 |
| Capacity mode: Provisioned | throughput 제한과 scaling 의사결정이 명시됨 |
| IncomingRecords graph | 피크 ingestion이 실제로 발생함 |
| Incoming data graph | record volume뿐 아니라 byte throughput도 발생함 |
| PutRecords latency | producer write latency 관찰 가능 |
| Write throughput exceeded / throttled records | 피크 부하에서 병목 후보를 관찰 가능 |
| PutRecords failed records: 0% | retry 이후 최종 전송 실패 없음 |

Kinesis 화면에서 `GetRecords` 계열 그래프가 비어 있을 수 있는데, 이는 producer만 실행하면 read metric이 생성되지 않기 때문이다. consumer script를 함께 실행해야 GetRecords latency, iterator age, read count가 나타난다. 이번 보고서에서는 producer ingestion evidence와 별도로 latency CSV를 consumer evidence로 사용한다.

### 6.3 S3 Raw Zone

캡처: raw bucket `peakorder-insight-dev-raw-87d26f49`

Raw bucket에는 다음 구조가 확인되었다.

```text
inventory/
orders/
products/
```

주문 이벤트는 다음 경로에 적재되었다.

```text
s3://peakorder-insight-dev-raw-87d26f49/orders/dt=2026-06-20/order_events.jsonl
```

캡처 기준 파일 크기는 66.5 MB이며, 이는 Kinesis replay 이후 raw data lake zone에 원천 이벤트가 보존되었음을 의미한다.

### 6.4 S3 Lakehouse and Serving Exports

캡처: lakehouse bucket `peakorder-insight-dev-lakehouse-87d26f49`

Lakehouse bucket에는 다음 구조가 생성되었다.

```text
checkpoints/
exports/
jars/
jobs/
paimon/
```

이 구조는 단순 결과 파일 저장소가 아니라 Spark job 실행 자산, Paimon runtime jar, checkpoint, serving export, lakehouse table state가 분리되어 있음을 보여준다.

Serving export는 JSON과 Parquet 두 형식으로 생성되었다.

```text
exports/json/order_item_events/
exports/json/peak_order_alerts/
exports/json/product_demand_daily/
exports/json/product_leaderboard/
exports/json/store_order_pressure_hourly/

exports/parquet/order_item_events/
exports/parquet/peak_order_alerts/
exports/parquet/product_demand_daily/
exports/parquet/product_leaderboard/
exports/parquet/store_order_pressure_hourly/
```

JSON export는 frontend dashboard에서 읽기 쉬운 serving format이고, Parquet export는 Glue/Athena 계열 분석에 적합한 columnar format이다.

### 6.5 Glue Data Catalog

캡처: Glue database `peakorder_insight_dev`

Glue에는 5개 table이 등록되어 있다.

| Table | Format | Role |
|---|---|---|
| `raw_order_events_json` | JSON | raw S3 order event catalog |
| `product_demand_daily` | Parquet | 상품별 demand/gross sales serving table |
| `product_leaderboard` | Parquet | dashboard leaderboard serving table |
| `store_order_pressure_hourly` | Parquet | store-hour pressure ratio serving table |
| `peak_order_alerts` | Parquet | PM/SRE alert queue serving table |

`raw_order_events_json` table은 raw bucket의 `orders/` location을 가리키며, schema에는 `event_id`, `order_id`, `customer_id`, `store_id`, `event_type`, `event_time`, `items`가 포함된다.

`peak_order_alerts` table은 `alert_id`, `store_id`, `hour_start`, `order_count`, `baseline_order_count`, `pressure_ratio`, `severity`, `reason`, `detected_at`을 포함한다. 이 table은 PM dashboard의 customer-impact alerts와 action queue의 근거가 된다.

### 6.6 EMR Serverless

EMR Serverless는 raw validation, lakehouse bootstrap, data loading, peak detection, serving export를 수행하는 Spark processing layer이다.

보고서에는 다음 job group을 구분해 쓰는 것이 좋다.

| Job type | Purpose | Report interpretation |
|---|---|---|
| Raw validation | raw JSONL row count and invalid record check | 데이터 품질 검증 |
| Paimon bootstrap/load | lakehouse table creation and append load | 최신 상태 테이블 구성 |
| Peak pressure detection | store-hour pressure and alert derivation | 운영 알림 생성 |
| Materialize views | JSON/Parquet serving export | dashboard/Glue serving layer 생성 |

EMR Studio에 남은 실패 로그가 `PARSE_SYNTAX_ERROR`라면 이를 스킵할 필요는 없다. 오히려 Spark SQL dialect와 Paimon DDL 호환성을 맞추는 과정에서 발생한 현실적인 트러블슈팅 근거로 사용할 수 있다.

권장 서술은 다음과 같다.

> 초기 Paimon table bootstrap job에서 Spark SQL parser가 특정 DDL syntax를 처리하지 못해 `PARSE_SYNTAX_ERROR`가 발생했다. 이는 EMR Serverless Spark 런타임과 Paimon DDL 표현 방식 사이의 호환성 문제로 판단했다. 이후 append-compatible table definition과 S3에 업로드한 Paimon Spark runtime jar를 사용하는 방식으로 전환했고, bootstrap/load/detect job을 성공시켜 lakehouse table state와 serving export를 생성했다.

이렇게 쓰면 단순한 코드 실수처럼 보이지 않고, managed Spark 환경에서 외부 table format을 붙일 때 발생하는 runtime compatibility 이슈를 해결한 사례가 된다.

### 6.7 CloudWatch Logs

캡처: CloudWatch log groups

확인된 log group은 다음과 같다.

```text
/aws/emr-serverless
/aws/peakorder/peakorder-insight-dev/pipeline
```

CloudWatch Logs는 EMR Serverless job의 stderr/stdout, pipeline validation, troubleshooting evidence를 남기는 관찰성 계층이다. private subnet 기반 job에서 로그 전송이 실패하면 원인 파악 자체가 어려워지기 때문에, CloudWatch Logs endpoint와 IAM permission은 단순 부가 설정이 아니라 운영 가능한 data platform의 필수 구성이다.

### 6.8 CloudWatch Alarm

캡처: `peakorder-insight-dev-kinesis-peak-ingestion`

Alarm은 Kinesis `IncomingRecords` metric을 기준으로 설정되었다.

| Field | Value |
|---|---|
| Namespace | AWS/Kinesis |
| Metric | IncomingRecords |
| Statistic | Sum |
| Period | 1 minute |
| Threshold | IncomingRecords >= 40,000 |
| Datapoints to alarm | 1 out of 1 |
| StreamName | peakorder-insight-dev-order-events |

캡처에서 threshold line을 넘는 구간이 보이므로, 피크 replay가 CloudWatch alarm 기준으로도 감지 가능한 수준이었음을 보여준다. 현재 state가 OK여도 문제가 아니다. missing data treatment가 not breaching으로 설정되어 있고, 피크가 지나간 뒤에는 정상 상태로 돌아오는 것이 운영적으로 자연스럽다.

### 6.9 VPC and Endpoints

캡처: VPC resource map and endpoint list

VPC는 private subnet 2개와 S3 gateway endpoint, CloudWatch Logs interface endpoint로 구성되어 있다.

| Resource | Evidence |
|---|---|
| VPC | `peakorder-insight-dev-vpc`, CIDR `10.42.0.0/16` |
| Private subnets | ap-northeast-2a, ap-northeast-2c |
| S3 endpoint | `peakorder-insight-dev-s3-endpoint`, Gateway, Available |
| CloudWatch Logs endpoint | `peakorder-insight-dev-logs-endpoint`, Interface, Available |

이 구성은 EMR Serverless job이 private network 안에서 S3 lakehouse와 CloudWatch Logs에 접근할 수 있게 하는 기반이다. 특히 S3 endpoint는 raw/lakehouse bucket 접근을, Logs endpoint는 job troubleshooting과 운영 로그 수집을 가능하게 한다.

## 7. Data Quality and Business Semantics

### 7.1 Data Quality

Raw validation job의 목적은 "파일이 존재한다"가 아니라 "분석 가능한 주문 이벤트인가"를 확인하는 것이다. 검증 기준은 다음과 같이 정의할 수 있다.

| Check | Purpose |
|---|---|
| total record count | replay target과 raw landing 결과 일치 확인 |
| invalid record count | schema-level or required field failure 확인 |
| error ratio | dashboard/alert 결과 신뢰도 판단 |

이번 실험에서는 전체 order event count가 281,660건으로 유지되며, serving layer에도 product demand, store pressure, peak alerts가 생성되었다.

### 7.2 PM KPI Logic

PM dashboard는 기술 지표를 그대로 노출하지 않고, 제품/운영 의사결정으로 변환한다.

| KPI | Formula / Basis | Decision rule |
|---|---|---|
| Peak demand concentration | peak-window orders / total orders | 60% 이상이면 lunch/dinner가 business day를 지배 |
| Store pressure ceiling | max store-hour orders / baseline | 2x intervention, 3.5x critical |
| Peak revenue at stake | avg order value x peak orders | 피크 대응 우선순위 산정 |
| Demand driver concentration | top SKU units and sales | 재고/번들/프로모션 결정 |
| Alert burden | count of peak pressure alerts | PM action queue 필요성 판단 |
| Decision freshness | Kinesis publish-to-read latency | 3초 미만이면 short peak window 대응 가능 |

이 기준은 dashboard를 "예쁜 화면"이 아니라, 피크 운영 의사결정의 기준표로 만든다.

## 8. Troubleshooting Narrative

### 8.1 Kinesis PutRecords Partial Failure

초기 대량 replay 과정에서 `Kinesis PutRecords failed for ... records` 형태의 오류가 발생했다. Kinesis `PutRecords` API는 batch 전체가 성공/실패로만 끝나는 것이 아니라, 일부 record만 실패할 수 있다. 따라서 단순히 exception을 발생시키면 실제로는 재시도 가능한 transient failure도 전체 replay 실패로 끝난다.

조치:

1. 실패 record만 골라 재시도하도록 producer를 수정했다.
2. `--max-retries`, `--retry-base-ms` 옵션을 추가했다.
3. exponential backoff로 retry pressure를 완화했다.

결과:

최종 replay에서 281,660건이 publish되었고, progress CSV 기준 failed_records 합계는 0건이다.

### 8.2 EMR Serverless Paimon DDL Syntax Error

EMR Studio에 남은 에러는 다음 유형이다.

```text
Job failed, please check complete logs in configured logging destination.
ExitCode: 1.
[PARSE_SYNTAX_ERROR] Syntax error at or near '('
```

이 에러는 실패 증거로 사용할 수 있다. 다만 보고서에서는 "코드 오타"가 아니라 "Spark SQL runtime과 Paimon DDL syntax를 맞추는 과정"으로 해석해야 한다.

Root cause:

- EMR Serverless Spark parser가 초기 Paimon table DDL의 일부 syntax를 처리하지 못했다.
- Paimon은 Spark extension/catalog 설정과 runtime jar가 필요하므로, managed EMR 환경에서는 로컬 Spark보다 package/runtime 문제가 더 잘 드러난다.

Resolution:

- Paimon Spark runtime jar를 S3 lakehouse bucket의 `jars/` 경로에 업로드했다.
- EMR Serverless job submit 시 `--jars`와 Spark catalog/extension config를 명시했다.
- table 정의를 append-compatible 형태로 조정했다.
- 이후 bootstrap/load/detect job을 성공시켜 Paimon warehouse와 serving export를 생성했다.

Report message:

> 실패 job은 제거할 대상이 아니라 개선 과정을 보여주는 근거다. 최종 성공 캡처와 함께 배치하면, managed Spark 환경에서 lakehouse table format을 붙이기 위해 runtime jar, catalog config, SQL dialect를 조정한 사례로 설명할 수 있다.

### 8.3 Private Subnet Observability

Private subnet에서 Spark job을 실행하면 외부 인터넷 접근이나 AWS service endpoint 접근이 제한될 수 있다. 이 프로젝트에서는 S3 gateway endpoint와 CloudWatch Logs interface endpoint를 구성해 private processing job이 S3와 CloudWatch에 접근할 수 있도록 했다.

이 경험은 데이터 파이프라인이 단순 코드 실행이 아니라 network/IAM/observability까지 포함한 운영 시스템임을 보여준다.

## 9. Evaluation

### 9.1 Does the Architecture Fit the Problem?

결론적으로, 이 구조는 문제에 적합하다.

첫째, Kinesis는 bursty order event를 받아들이는 streaming ingestion layer로 동작했다. CloudWatch IncomingRecords graph와 alarm threshold crossing은 피크 ingestion이 실제로 발생했음을 보여준다.

둘째, S3 raw bucket은 원천 데이터를 보존한다. 이는 replay, backfill, audit, schema evolution의 기반이다.

셋째, EMR Serverless와 Paimon lakehouse는 raw event를 운영 상태 테이블과 serving export로 변환한다. Glue Data Catalog는 이 결과를 관리 가능한 table로 노출한다.

넷째, latency evidence는 실시간 구조의 합리성을 뒷받침한다. 전체 p95 약 2.03초, 피크 p95 약 2.06초는 피크 상황에서도 PM/SRE dashboard가 "지금 보고 대응하는" 도구가 될 수 있음을 보여준다.

### 9.2 What the Result Does Not Prove

이번 결과가 production readiness 전체를 증명하는 것은 아니다. 다음은 별도 검증이 필요하다.

| Area | Why it matters |
|---|---|
| multi-shard scaling | 더 큰 traffic에서 shard 수와 partition key skew 검증 필요 |
| long-running consumer | 단기 replay가 아니라 지속 소비 안정성 검증 필요 |
| exactly-once semantics | 중복 이벤트, late event, idempotent write 처리 필요 |
| cost optimization | EMR Serverless, Kinesis shard, S3 request cost 추정 필요 |
| security hardening | IAM least privilege, bucket policy, encryption, secret rotation 보강 필요 |
| production alarm routing | SNS subscription, PagerDuty/Slack 연동 등 실제 on-call flow 필요 |

하지만 portfolio project의 목적이 "피크 주문 상황을 real-time lakehouse architecture로 설계하고 AWS에서 동작 증거를 확보하는 것"이라면, 현재 결과는 충분히 강한 완성도를 가진다.

## 10. Screenshot Appendix

> 아래 항목에 캡처 이미지를 삽입한다.

1. Frontend PM dashboard
   - Total orders: 281,660
   - Peak-window orders: 200,000
   - Decision freshness: 1,337 ms
   - Store pressure ceiling: 4.34x

2. Kinesis stream monitoring
   - Active stream
   - Incoming data / Incoming records spike
   - PutRecords latency
   - Write throughput exceeded / throttled records

3. S3 raw bucket
   - `orders/dt=2026-06-20/order_events.jsonl`
   - file size 66.5 MB

4. S3 lakehouse bucket
   - `checkpoints/`, `exports/`, `jars/`, `jobs/`, `paimon/`

5. S3 serving exports
   - `exports/json/*`
   - `exports/parquet/*`

6. Glue database
   - `peakorder_insight_dev`
   - 5 registered tables

7. Glue raw table schema
   - `raw_order_events_json`
   - JSON schema and S3 location

8. Glue alert table schema
   - `peak_order_alerts`
   - pressure ratio and severity columns

9. CloudWatch Logs
   - `/aws/emr-serverless`
   - `/aws/peakorder/peakorder-insight-dev/pipeline`

10. CloudWatch Alarm
    - `peakorder-insight-dev-kinesis-peak-ingestion`
    - `IncomingRecords >= 40000`

11. VPC resource map
    - private subnets
    - S3 endpoint

12. VPC endpoints list
    - S3 gateway endpoint
    - CloudWatch Logs interface endpoint

13. EMR Serverless failed job
    - `PARSE_SYNTAX_ERROR`
    - use as troubleshooting evidence

14. EMR Serverless success job
    - final bootstrap/load/detect/materialize jobs

## 11. Final Conclusion

PeakOrder Insight는 주문 피크라는 명확한 운영 문제에서 출발해, Kinesis streaming ingestion, S3 raw/lakehouse storage, EMR Serverless Spark processing, Paimon table state, Glue metadata catalog, CloudWatch observability, role-based dashboard까지 연결한 end-to-end AWS 데이터 엔지니어링 프로젝트이다.

가장 중요한 성과는 세 가지다.

1. 데이터가 피크 형태로 실제 Kinesis에 유입되었다.
2. 피크 상황에서도 publish-to-read p95 latency가 약 2.06초로 유지되어 real-time dashboard의 합리성을 입증했다.
3. raw data, lakehouse export, Glue schema, CloudWatch alarm, VPC endpoint, troubleshooting evidence가 모두 AWS UI 캡처로 남아 보고 가능한 형태가 되었다.

따라서 이 프로젝트는 단순히 AWS 서비스를 나열한 웹사이트 제작이 아니라, 피크 주문이라는 운영 문제를 데이터 플랫폼 관점에서 모델링하고 검증한 real-time lakehouse case study로 정리할 수 있다.

