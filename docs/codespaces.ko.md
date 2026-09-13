# Codespaces에서 실제 감상 앱 체험

**클라우드 체험용, 민감 자료 업로드 금지.** 로컬 앱과 같은 UI·API·SQLite·영상
저장 경로를 사용하며, 별도 `.codespaces-data/` 보관함만 엽니다. 개인 영상·기존 DB·
API 키를 가져오지 마세요. 합성 샘플에는 실제 대화가 없으며 자막은 사람이 작성한
체험 문구입니다. ASR·번역·영상 향상 품질을 보여 주는 자료가 아닙니다.

## 만들기와 시작

1. GitHub의 `seoji2005/media-server`에서 **Code → Codespaces → … → New with options**를
   누릅니다. 병합 전에는 **Branch: `feat/codespaces-viewing`**, 병합 뒤에는 `main`을
   선택합니다. **Dev container: Media Clarity · 클라우드 감상 체험**, **Machine type: 2-core**로
   생성합니다. 새 과금 설정·카드 등록·유료 한도 증액은 필요 조건이 아닙니다.
   사용 가능 할당량이 없어 결제를 요구하면 생성하지 마세요.
2. 환경 준비가 끝날 때까지 기다립니다. Python 3.12 이미지에서 FFmpeg·GitHub CLI와
   현재 `requirements.txt`의 감상용 의존성만 설치합니다. 모델·GPU·추론 키는 설치하지
   않습니다. 도구 설치와 Python 설치는 각각 전체 5분·출력 무진행 2분 상한이며
   연결·다운로드 재개 자동 재시도는 0입니다. GitHub가 관리하는 이미지 받기 시간은 별도입니다.
3. 터미널에서 저장소 루트 기준으로 실행합니다.

   ```bash
   bash scripts/start_codespaces.sh
   ```

4. **PORTS** 탭의 **8765** 행에서 **Visibility: Private**를 확인하고 지구본
   **Open in Browser**를 누릅니다. GitHub 로그인 후 나타나는 주소는
   `https://<이 Codespace 이름>-8765.app.github.dev`입니다. 이 정확한 HTTPS 주소만
   체험용 출처로 허용합니다. `Public`이나 `Private to Organization`으로 바꾸지 마세요.

앱 시작마다 GitHub CLI로 8765를 Private으로 제한하고 실제 포트 목록·주소를 확인합니다.
확인이 실패하면 서버를 시작하지 않습니다. 연결된 Work 도구에는 Codespace 생성·접속
기능이 없어 실제 계정에서의 생성·인증·포트 연결은 미검증입니다. 아래 검증 구분을 참고하세요.

## 3분 체험 순서

1. **보관함 → 보랏빛 산책**을 엽니다. 32초 합성 영상에서 재생·일시정지·타임라인 탐색을 합니다.
2. **자막**에서 한국어와 영어를 번갈아 선택합니다. **자막 준비**에서는 공개·합성
   SRT/VTT를 직접 가져와 선택할 수 있습니다. AI 자막 생성·번역은 체험 모드에서 숨기고
   서버에서도 차단합니다. 한국어를 선택한 뒤 **자막 감상 설정 → 0.5초 늦추기**를
   누릅니다. 자막은 원본을 수정하지 않고 표시 시간만 바꿉니다.
3. **장면 찾기 → 선택한 자막에서 검색**에 `하늘 아래 천천히`를 입력합니다.
   4.0–6.0초와 6.2–9.5초의 **서로 다른 두 자막에 걸친 문장**이 검색됩니다.
   결과를 눌러 보정한 시간의 해당 장면으로 이동합니다. 검색어는 브라우저 안에서만 처리합니다.
4. 18초쯤에서 멈추고 **보관함**으로 돌아갑니다. **이어보기**로 다시 열고 위치와 자막을
   확인합니다. 새로고침 후에도 보관함에서 같은 영상을 열면 위치·선택·시간 보정이 복원됩니다.
5. 터미널에서 `Ctrl+C`로 앱을 종료하고 같은 시작 명령을 다시 실행합니다. 브라우저를
   새로고침하고 같은 영상을 엽니다. 재시작할 때 세션 토큰은 교체되고 감상 기록은 유지됩니다.

초록빛 산책으로 빠르게 전환해 다른 영상의 기록과 구분되는지도 체험할 수 있습니다.
샘플 초기화는 앱 시작에 포함됩니다. 원본 SHA256과 기존 가져오기 영수증을 검증해
영상·자막 중복을 막으며, 제목 변경·사용자 자막·시청 위치·감상 설정을 덮어쓰지 않습니다.
샘플이 바뀌거나 기존 미식별 데이터가 있으면 덮어쓰지 않고 시작을 중단합니다.

## 종료·재시작·데이터 보관

- **앱만 종료:** 터미널 `Ctrl+C`. 다시 시작하려면 같은 명령을 실행합니다.
- **클라우드 사용 종료:** 앱을 종료한 뒤 명령 팔레트 `Ctrl+Shift+P`에서
  **Codespaces: Stop Current Codespace**. 브라우저 탭을 닫는 것만으로는 정지하지 않습니다.
- **이어서 체험:** [내 Codespaces](https://github.com/codespaces)에서 기존 항목을 열고
  시작 명령을 실행합니다. 새 Codespace를 만들면 별도 보관함으로 시작합니다.
- 데이터는 저장소의 `.codespaces-data/`에 있고 Git에서 제외됩니다. `/workspaces` 아래라
  같은 Codespace의 중지·재시작·컨테이너 재빌드 후에도 유지됩니다. 필요하면 **앱을 종료한
  뒤** 이 폴더 전체를 내려받으세요. 실행 중 SQLite 파일 하나만 복사하지 마세요.
- **완전 종료:** 필요한 체험 결과를 보관한 뒤 내 Codespaces의 해당 항목 **… → Delete**.
  삭제하면 체험 데이터도 사라집니다. GitHub의 보존 기간이 지나 자동 삭제될 수도 있습니다.
  중지 상태에도 저장 공간 사용량은 남습니다. 이 설정은 과금·보존 기간·유료 한도를 바꾸지 않습니다.

## 실패했을 때

- 준비가 끝나지 않았다면 설치 로그의 마지막 오류를 확인하세요. 원인을 해결한 뒤에만
  `python3 scripts/setup_codespaces.py`를 다시 실행합니다. 모델 설치 명령은 사용하지 않습니다.
- `codespaces_private_port_unverified`: PORTS의 8765·Private 여부와 GitHub Codespaces
  권한을 확인합니다. 시작 스크립트는 인증 값을 출력하지 않습니다. API 키나 토큰을 붙여
  넣거나 Public으로 바꾸어 해결하지 마세요. 권한 때문에 확인할 수 없으면 체험을 중단합니다.
- 출처 오류: 해당 Codespace의 PORTS에서 주소를 다시 여세요. Host/Origin 검사를 끄거나
  `X-Forwarded-Host`·와일드카드 예외를 추가하지 않습니다. 포트 프로토콜은 내부 앱에 맞는
  **HTTP**를 유지합니다. 외부 브라우저 주소의 **HTTPS**와는 별개입니다.
- `already_running`: 실행 중인 앱 터미널을 사용하거나 `Ctrl+C`로 종료합니다. 잠금 파일을
  삭제하거나 다른 앱을 강제 종료하지 마세요. 기존 데이터 충돌·샘플 변경 오류도 데이터를
  먼저 보존하고 원인을 확인해야 합니다.

## 보안·검증 범위

체험 모드는 `python -m media_clarity.codespaces --start`로만 명시적으로 시작합니다.
기본 `python -m media_clarity`의 로컬 실행 규칙은 유지합니다. 체험 모드는 loopback에
바인딩하고 정확한 Host·HTTPS Origin과 세션 토큰을 검사하며, 프록시 헤더를 신뢰하지 않습니다.
추론 API는 서버에서 차단하고 자막 작업자를 시작하지 않습니다. 샘플 가져오기·재생·수동
자막·설정 저장은 실제 제품 기능입니다. Fetch·대형 모델·GPU·유료 API 실행은 범위 밖입니다.

`tests/test_codespaces.py`는 실제 FFmpeg·파일·DB·앱 API를 쓰며 GitHub CLI·출처는 모의 검사입니다.
`python tests/codespaces_smoke.py`는 실제 TCP 서버·재시작 검사입니다. `--browser`는 CI의
Chrome으로 합성 영상·네이티브 자막·문장 검색·저장 복원을 검사하되 GitHub 전달 계층은
테스트 경계에서 모의합니다. 실제 Codespace 인증·HTTPS 전달이나 사람의 감상 평가를 대신하지 않습니다.
실행한 결과와 고정 리비전·독립 보안 검토는 PR에서 확인하세요.

공식 참고: [포트 전달](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace),
[환경 변수](https://docs.github.com/en/codespaces/developing-in-a-codespace/default-environment-variables-for-your-codespace),
[포트 공개 범위 CLI](https://cli.github.com/manual/gh_codespace_ports_visibility),
[중지·재빌드·삭제](https://docs.github.com/en/codespaces/about-codespaces/understanding-the-codespace-lifecycle).
