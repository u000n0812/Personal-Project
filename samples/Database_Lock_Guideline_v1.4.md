# Database Lock Guideline

문서번호: GL-DBL-004
버전: 1.4
적용일: 2024-05-20

## 1. 개요
DBL 은 Database Lock 을 의미한다.
Database Lock 은 임상 데이터의 수정이 더 이상 발생하지 않도록 데이터베이스를
잠그는 절차이며, 통계 분석 시작 전에 수행한다.

## 2. 용어
DB Lock, DBL, Database Lock 은 모두 동일한 의미로 사용한다.
Soft Lock 은 일부 권한만 제한하는 임시 잠금을 의미한다.
Hard Lock 은 모든 데이터 수정 권한을 제거하는 최종 잠금을 의미한다.

## 3. DB Lock 전 확인 항목
DB Lock 전에 아래 항목을 모두 확인하고 Checklist 에 서명한다.
- 모든 Data Query 가 종결(Closed)되었는지 확인한다.
- SAE Reconciliation 이 완료되었는지 확인한다.
- External Data Reconciliation 이 완료되었는지 확인한다.
- Medical Coding 이 완료되고 승인되었는지 확인한다.
- Protocol Deviation 검토가 완료되었는지 확인한다.
- 모든 CRF 페이지가 조사자 서명 완료 상태인지 확인한다.
- Data Management Plan 에 정의된 Edit Check 가 모두 수행되었는지 확인한다.

## 4. DB Lock 승인
DB Lock 은 다음 담당자의 승인을 받아야 한다.
Data Manager, 통계 담당자, Medical Monitor, Project Manager 의 승인이 필요하다.
승인은 DB Lock Checklist 에 서명하는 방식으로 진행한다.

## 5. DB Lock 수행
승인 완료 후 System Administrator 가 데이터베이스 권한을 변경한다.
Lock 수행 일시와 수행자는 시스템 로그로 보관한다.
Lock 이후 데이터 추출은 읽기 전용 계정으로만 수행한다.

## 6. Unlock 절차
DB Lock 이후 데이터 수정이 필요한 경우 Unlock 절차를 따른다.
Unlock 요청서에는 수정 사유, 대상 데이터, 영향 범위를 기재한다.
Unlock 은 Project Manager 와 Medical Monitor 의 승인을 받아야 한다.
Unlock 후 수정이 완료되면 3장의 확인 항목을 다시 점검하고 재Lock 한다.

## 7. 기록
DB Lock 및 Unlock 이력은 Trial Master File 에 보관한다.
