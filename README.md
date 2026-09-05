# Media Clarity · media-server

로컬 영상 처리·감상 앱을 만들기 위한 최소 개발 하네스입니다.
**현재는 하네스만 있으며 앱·ASR·번역·업스케일은 구현하지 않았습니다.**

목표는 2026년 10월 중순 Windows 11 / Ryzen 5 7500F / RAM 64 GB /
RTX 4070 SUPER 12 GB에서 실제로 감상할 수 있는 제품입니다.

## 시작

Python 3.12 이상과 Git을 사용합니다. 하네스에는 추가 Python 패키지가 필요 없습니다.

```text
python scripts/harness.py check
python scripts/harness.py status
python scripts/harness.py run test
python scripts/harness.py run start
```

- `check`: 하네스 설정·필수 문서·로컬 문서 링크 검사. 제품 검증이 아닙니다.
- `status`: 현재 Git revision·변경 유무·등록된 실행 명령 확인. 파일 내용이나 개인 경로는 출력하지 않습니다.
- `run`: `harness.json`의 실제 명령을 shell 없이 실행하고 종료 코드를 전달합니다.
  아직 제품 명령은 `null`입니다. 미설정 명령은 `NOT_CONFIGURED`, 종료 코드 2로
  실패합니다. 빈 테스트나 가짜 서버로 성공을 만들지 않습니다.

구현 착수 후 실제 테스트·시작 명령을 `harness.json`에 등록합니다.
시작 명령은 원칙적으로 loopback에만 바인딩합니다. `harness.json`은 신뢰하는
저장소 코드와 동일하게 취급하며, 외부에서 받은 설정을 검토 없이 실행하지 않습니다.

## 작업 방식

한 명의 주 구현자가 범위 5줄을 정하고 구현→실행→검증까지 진행합니다.
원본 안전·영속성·개인정보·주관적 화질에는 독립 평가를 선택적으로 사용합니다.
일반 작업의 반복 승인은 요구하지 않고 최종 병합·출시는 오너가 결정합니다.

- 정책과 근거: [docs/engineering.md](docs/engineering.md)
- 제품 범위·기본 구조: [docs/product.md](docs/product.md)
- donor 재사용 판단: [docs/donor.md](docs/donor.md)
- 다음 대화의 시작점: [docs/current.md](docs/current.md)

작업 재개 예시: “AGENTS.md와 docs/current.md를 읽고 현재 Git 상태에서 다음
한 작업을 검증까지 진행하라.” 하네스만 수정하라는 별도 지시가 있으면 앱을 만들지 않습니다.
