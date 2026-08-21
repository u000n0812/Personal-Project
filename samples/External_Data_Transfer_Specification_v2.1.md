# External Data Transfer Specification

문서번호: SPEC-EDT-002
버전: 2.1
적용일: 2024-03-01

## 1. 목적
본 문서는 External Data(외부 데이터)를 Vendor 또는 외부 기관과 주고받을 때
준수해야 하는 전달 절차, 보안 요건, 승인 절차를 정의한다.

## 2. 적용 범위
본 문서는 모든 프로젝트의 External Data 수신 및 송신에 적용한다.
Lab Data, ECG Data, PK Data, IRT Data 등 외부에서 생성되는 모든 데이터가 포함된다.

## 3. 역할과 책임
Data Manager 는 External Data 전달 계획을 수립하고 전달 이력을 관리한다.
Data Provider 는 데이터 파일을 생성하고 규정에 맞게 암호화하여 전달한다.
Project Manager 는 최종 전달 승인을 수행한다.

## 4. 전달 준비
### 4.1 Data Transfer Agreement
External Data 전달 전에 Data Transfer Agreement(DTA)가 체결되어 있어야 한다.
DTA 에는 전달 주기, 파일 형식, 전달 담당자, 보안 요건이 포함되어야 한다.

### 4.2 Test Transfer
정식 전달 이전에 반드시 Test Transfer 를 1회 이상 수행한다.
Test Transfer 결과는 Data Manager 가 확인하고 기록으로 남긴다.

## 5. Data Transfer
### 5.1 전달 방법
데이터는 회사가 승인한 sFTP 서버를 통해서만 전달한다.
개인 이메일, 개인 클라우드, USB 를 이용한 전달은 금지한다.

### 5.2 파일 명명 규칙
파일명은 [ProjectID]_[DataType]_[YYYYMMDD]_[Version] 형식으로 작성한다.
예: ABC123_LAB_20240315_v1.

### 5.3 Encryption Rule
Data Provider 는 파일을 반드시 암호화하여 전달한다.
암호화 방식은 AES-256 이상을 사용한다.
Password 는 파일과 함께 보내지 않으며, 반드시 별도의 Email 로 전달한다.
Password 는 최소 12자리 이상이며 영문 대소문자, 숫자, 특수문자를 포함한다.
Password 는 전달 건마다 새로 생성하며 재사용하지 않는다.

### 5.4 전달 확인
수신자는 파일 수신 후 24시간 이내에 수신 확인 회신을 보낸다.
수신 확인이 없으면 Data Manager 가 Data Provider 에게 재확인을 요청한다.

## 6. 승인 절차
External Data 전달은 다음 순서로 승인한다.
1) Data Manager 검토
2) 통계 담당자 확인 (분석용 데이터인 경우)
3) Project Manager 최종 승인
승인 기록은 프로젝트 문서 관리 시스템에 보관한다.

## 7. 오류 처리
전달된 파일이 손상되었거나 규격과 다른 경우 즉시 전달을 중단한다.
Data Manager 는 Issue Log 에 기록하고 Data Provider 에게 재전달을 요청한다.
재전달 시에도 5.3 의 암호화 규칙을 동일하게 적용한다.

## 8. 기록 보관
전달 이력은 프로젝트 종료 후 최소 5년간 보관한다.
전달 이력에는 전달 일시, 파일명, 담당자, 승인자가 포함된다.
