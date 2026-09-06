# Media Clarity · media-server

내 기기의 영상을 가져와 보관하고 감상하는 개인용 로컬 앱입니다.
**파일 선택 → 보관함 → 자막 선택 → 재생·탐색 → 시청 위치 저장·복원.**
원본은 읽기만 하며 앱 보관 공간에 별도 사본을 만듭니다. 영상·제목·썸네일·
시청 기록은 외부로 전송하지 않습니다. 외부 CDN·폰트·분석 도구도 사용하지 않습니다.

10월 Windows/RTX 감상 제품을 위한 진행 중 체크포인트입니다. UTF-8·CP949/EUC-KR SRT 가져오기·
자막 버전 선택, 선택한 자막의 문장 검색·장면 이동, 로컬 ASR/번역 연결과 처리 재개를
추가했습니다. 문장 단위 번역과 구간 배치 저장을 사용하며, 번역 실패 구간은 `[원문]`으로
남겨 감상할 수 있습니다. **새 자막 만들기**는 기존 자막을 보존합니다.
새 생성 자막은 번역 문장을 보존하면서 두 줄 표시로 나눕니다. 너무 빠르거나 긴 구간은
확인 안내를 표시합니다. SRT의 순서·빈 구간·영상 끝 초과도 보정 내용을 알려 줍니다.
[가독성 기준과 실제 브라우저 확인](docs/subtitle-readability.md)을 참고하세요.
음성 검출은 로컬 PyTorch 모델을 사용하고 진단 전송 문제가 있던 ONNX Runtime은 로드하지
않습니다. Windows의 일괄 차단은 제거했지만 **실제 Windows/RTX 실행은 아직 미검증**입니다.
**감상 취향**에서 선호와 추천 포함 여부를 저장하면 **추천**에서 다른 영상을 고를 수
있습니다. [첫 로컬 추천](docs/recommendations.md)은 포함한 영상의 제목 단어와 직접 표시한
선호만 사용합니다. 시청 기록·자막은 학습에 넣지 않으며, 새 영상은 기본적으로 제외됩니다.
**장면 찾기 → 화면 내용으로 찾기**에서 한국어로 화면을 묘사하면, 이 영상의 미리보기에서
비슷한 후보와 시점을 찾아 재생할 수 있습니다. [로컬 모델 준비·사용·실측 한계](docs/scene-search.md)를
확인하세요. 없는 장면도 후보로 나오거나 짧은 장면을 놓칠 수 있습니다.
추천 품질, 향상·영상 내용 분석의 최종 품질과 Windows 감상 검증은 아직 완료하지 않았습니다.
[첫 향상 후보 실측](docs/enhancement-spike.md)은 공개 실사 영상을 CPU에서 비교한 개발용
실험입니다. 압축 영상에서의 품질 한계가 확인되어 앱의 기본 프리셋으로 채택하지 않았습니다.
[자막 사용·모델 준비·복구 한계](docs/subtitles.md)를 먼저 확인하세요. 다운로드·AI 생성·NAS는
이번 릴리스에서 제외합니다. [제품 범위](docs/product.md)를 따릅니다.

## 설치와 실행

Python **3.12**, FFmpeg와 ffprobe가 필요합니다. FFmpeg는 신뢰하는 배포본을
설치해 두 실행 파일이 `PATH`에 보이게 하세요. 아래 버전 확인이 모두 성공해야 합니다.
앱 안에서도 누락을 알리고 `doctor`는 경로 없이 사용 가능 여부만 보여줍니다.
보관함의 **설정 → 자막 실행 환경 → 실행 환경 확인**에서 선택 장치와 자막 실행 환경을
확인할 수 있습니다. 모델 설치 후에는 앱을 종료하고 `doctor --models`로도 확인할 수
있습니다. 기본 `doctor`와 원본 감상은 자막 모델 없이 사용할 수 있습니다.

Windows PowerShell, 저장소 폴더에서:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
.\.venv\Scripts\python -m media_clarity doctor
.\.venv\Scripts\python -m media_clarity
```

macOS/Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
ffmpeg -version
ffprobe -version
.venv/bin/python -m media_clarity doctor
.venv/bin/python -m media_clarity
```

브라우저에서 **http://127.0.0.1:8765**를 열고 **영상 가져오기**를 누르세요.
끌어놓기도 가능합니다. 한 번에 한 개를 가져오며 진행률 다음에 무결성·형식 검증을
수행합니다. 복사본 해시 확인 때문에 큰 파일은 전송 후에도 시간이 걸립니다.
Ctrl+C로 종료하고 같은 명령으로 다시 실행하면 보관함과 저장한 위치를 복원합니다.
서버 재시작 후 웹페이지는 새로고침하세요. 포트 충돌 시 `--port 8766`을 사용합니다.
호스트는 항상 `127.0.0.1`이며 LAN 공개·클라우드 배포 기능은 없습니다.

MP4/MOV·MKV의 **H.264 8-bit 4:2:0**와 WebM/Matroska의
**VP8/VP9 8-bit 4:2:0 + Opus/Vorbis**를 지원합니다. 무음 영상도 가능합니다.
H.264 MKV는 영상을 재인코딩하지 않고 MP4로 리먹스합니다. 선택한 오디오가 AC3/EAC3·DTS·
FLAC·Opus/Vorbis·지원 PCM이면 AAC 192 kbit/s 스테레오로 변환합니다. AAC/MP3는 복사합니다.
기본은 첫 번째 트랙이며, 감상 화면의 **오디오 → 들을 음성 → 적용**으로 바꿀 수 있습니다.
오디오별 사본은 처음 한 번 준비하고 재사용합니다. 준비 실패 시 현재 재생을 유지합니다.
새 자막은 감상 중인 음성으로 만들고, 이미 시작한 작업은 시작 당시의 음성으로 재개합니다.
기존 자막은 오디오 번호와 함께 보존합니다. 전체 원본과 모든 트랙을 보관하며 HEVC/10-bit는 변환하지
않고 구분된 안내를 표시합니다. 비디오 트랙 한 개, 각 변 8,192픽셀 이하를 허용합니다.

가져온 뒤 필요한 재생용 사본을 자동 준비합니다. 실패해도 원본은 보관함에 남으며
해당 카드를 선택하면 재시도합니다. 기존 보관함은 처음 선택할 때 형식을 확인합니다.
준비 중에도 다른 준비된 영상은 볼 수 있습니다. 재생용 사본 크기만큼 공간이 더 필요하며
정확한 처리 퍼센트·중간 변환 재개는 아직 없습니다. 중단한 변환은 처음부터 재시도합니다.
[지원 범위·복구·검증](docs/compatible-renditions.md)을 참고하세요.
전체 프레임의 디코딩 무결성을 검사하지는 않습니다. 브라우저·OS 코덱 지원에 따라
재생이 달라질 수 있으며 **Windows 브라우저 재생은 아직 미검증**입니다.
native 재생 버튼·탐색 막대·전체 화면을 사용합니다. 자막 선택은 감상 화면에 바로 보이며,
**자막 준비**, **장면 찾기**, **감상 취향**을 펼치면 추가 기능을 사용할 수 있습니다.
자막 준비가 접혀 있어도 처리 상태와 확인할 구간 안내는 표시합니다.
**장면 찾기 → 시간별 미리보기**에서 필요할 때 작은 프레임을 만들고 선택한 시점으로
이동할 수 있습니다. 멈추거나 닫으면 현재 묶음까지 저장하며, 앱을 재시작해도 이어 만듭니다.
뒤의 장면이 보일 수 있으며, 일정 간격의 이미지 탐색입니다. 화면 내용으로 찾기는 이 표본을
검색하므로 짧은 장면을 놓칠 수 있습니다. [미리보기 동작과 실제 검증](docs/previews.md)을 참고하세요.

시청 위치는 약 4초마다, 일시정지·탐색·창을 닫을 때 저장합니다. 화면에 표시된 마지막
**저장됨** 위치가 복원 기준입니다. 강제 종료 시 마지막 미확인 몇 초는 남지 않을 수
있습니다. 끝까지 본 영상은 다음 재생에서 처음부터 시작합니다.

## 보관과 복구

기본 보관 폴더는 Windows `%LOCALAPPDATA%\MediaClarity`, Linux
`$XDG_DATA_HOME/media-clarity`(미설정 시 `~/.local/share/media-clarity`), macOS는
`~/.local/share/media-clarity`입니다. `--data-dir`로 저장소 밖의 별도 폴더를 지정할 수 있습니다.
원본 보관 공간과 추가 32 MiB 이상의 여유 공간이 필요합니다. 재생용 변환에는 영상 복사와
AAC·컨테이너 여유분을 더 확인합니다. 백업은 앱을 종료한 상태에서
이 폴더 전체를 보존하세요. 영상과 DB를 함께 보존해야 합니다.

- 동일 바이트의 재수입은 기존 항목·시청 기록을 유지합니다. 해시는 바이트 중복만 의미합니다.
- 수입 중단 후 다음 실행에서 staging/미등록 사본을 `recovery`에 격리 보존합니다.
  보관함에 자동 등록하지 않으며 원본에서 다시 가져올 수 있습니다.
- `files/<file_id>/original.mp4`, `original.mkv` 또는 `original.webm`이 없으면 누락 상태를 표시합니다.
  같은 파일 재수입도 거짓 성공 처리하지 않습니다. 앱을 종료하고 **해당 사본을 백업에서
  복원**하세요. 자동 재연결·삭제·재가져오기를 통한 복구 UI는 아직 없습니다.
- 재생 전 저장된 SHA-256과 사본 전체를 대조합니다. 첫 재생·서버 재시작·파일 변경·
  캐시 퇴출 후에는 큰 영상의 검증에 시간이 걸릴 수 있습니다. 이후 Range 요청은
  변경 metadata와 요청 구간의 검증된 블록 해시를 확인하며 매번 전체를 다시 읽지 않습니다.
  크기가 같은 변경도 검출하면 `managed_file_changed`로 거절하고 보관함에 표시합니다.
  재생 중 새 변경은 변경된 블록 전송 전에 연결을 실패시킵니다. 보관함 목록은 파일 존재와
  이미 발견된 오류만 표시하며 전체 영상의 무결성을 미리 검사하지 않습니다.
- 보관 폴더의 symlink·Windows junction을 거부합니다. 같은 폴더에서는 앱 프로세스
  하나만 실행합니다. 이는 별도 클라우드 Work의 직렬화 증거가 아닙니다.

원본의 복사 전후 파일 identity·해시까지 확인하려면, 서버를 종료하고 로컬 CLI를 사용할
수 있습니다. 브라우저 수입은 선택한 File의 전송 길이와 저장 사본 해시를 검증하며,
원본 디스크 경로·변경 전후 metadata 검증을 주장하지 않습니다.

```powershell
.\.venv\Scripts\python -m media_clarity import "D:\Videos\example.mp4"
```

CLI 성공 출력은 항목 ID와 중복 여부만 포함합니다. 로그에 경로·제목·쿼리·내용을
기록하지 않습니다. ffprobe/ffmpeg는 로컬 프로토콜·형식 allowlist, 시간·출력 제한으로
실행합니다. 로컬 Host·동일 Origin·메모리 세션 토큰으로 변경 요청을 제한합니다.
앱은 OS의 동일 사용자 권한이나 관리자에 대한 샌드박스가 아닙니다.

## 검증과 작업 방식

```sh
python -m pip install -r requirements-dev.txt
npm ci --prefix tests/ui --no-audit --no-fund
python scripts/harness.py run test
```

위 `python`은 활성화한 `.venv`의 Python이어야 합니다. 활성화하지 않을 때는 앞의
venv Python 명령으로 직접 테스트·시작하세요. 하네스도 호출한 Python을 그대로 사용합니다.
검증에는 Node.js **24**, FFmpeg/ffprobe와 설치된 **Chrome**이 필요합니다.
Edge를 쓰려면 `MEDIA_TEST_BROWSER_CHANNEL=msedge`, 별도 Chromium 실행 파일은
`MEDIA_TEST_BROWSER_EXECUTABLE` 환경 변수로 지정합니다. 실행 파일·코덱이 없으면 실패하며
브라우저 검사를 조용히 건너뛰지 않습니다. 실제 Windows/RTX 검증을 대신하지 않습니다.

기본 명령은 Python 검사 → 추천 포함 DOM 검사 7개 → 실제 브라우저 검사를 실행합니다.
브라우저 검사는 임시 폴더의 20초 H.264/AAC 합성 영상·한국어 SRT만 사용해 UI 가져오기,
native 자막, Range 재생, 탐색, 닫기/열기, 서버 프로세스 재시작 후 7초 위치 복원,
원본/보관 사본 보존과 빈 서버 로그를 확인합니다. 모델·개인 영상·API 키는 필요 없습니다.
DOM 검사는 mocked media/HTTP이며 디코딩 증거가 아닙니다.
좁은 변경에는 `python -m unittest discover -s tests -q` 또는
`npm test --prefix tests/ui`만 실행할 수 있습니다. 문서 링크 검사는 `python scripts/harness.py check`입니다.

[GitHub CI](.github/workflows/verify.yml)는 같은 명령을 Linux와 Windows Server 2025/CPU에서
실행하도록 준비했습니다. 두 작업 각각 최대 10분이며 모델 다운로드·캐시·artifact 업로드는 없습니다.
**현재 원격 실행은 비활성**입니다. 비공개 저장소의 무료 잔여량을 확인하거나 오너의 실행 비용
승인을 받은 뒤 repository Actions variable `MEDIA_CI_ENABLED=true`로 활성화합니다.
이 연결 도구는 계정 billing 조회를 허용하지 않습니다. Windows CI가 통과해도 Windows 11/RTX
실행·실제 소리·모니터 배율·감상 품질은 별도로 확인해야 합니다.

2026-09-06 검증: `2a45773`에서 위 기본 명령으로 Python **131개/39.861초**, DOM **7개**,
브라우저 최초/재시작 검사가 통과했습니다. 환경은 Python 3.12.13/Linux, FFmpeg 6.1.1,
Node 24.19.0, Playwright 1.63.0, 별도 Chromium 149 실행 파일입니다.
독립 검토에서 테스트 서버 포트 인계 중 다른 로컬 앱을 사용할 가능성을 발견했습니다.
`1abf072`는 자식이 소켓을 계속 소유하도록 수정했고, 해당 브라우저 검사를 다시 통과했습니다.
검토자도 경쟁 bind 거절·자식 종료·빈 로그를 확인했습니다. 이후 전체 Python/DOM 재실행은
하지 않았습니다. 원격 CI·Chrome·Windows·RTX·실제 소리·사람의 가독성 평가는 미검증입니다.
브라우저 재현 명령은 `python tests/browser_smoke.py`이며 cloud에서는 위 실행 파일 환경 변수를
지정했습니다. 장편·실모델 실험은 이 합성 검사와 별개입니다. [현재 인계](docs/current.md) 참고.

한 Work가 총괄·구현하고 위험한 변경에만 fresh reviewer subagent를 사용합니다.
GitHub는 checkpoint를 보관하며 두 Work 사이 이벤트 왕복은 사용하지 않습니다.
일상 수정·검증·Draft PR은 승인 범위이며 최종 병합·출시는 오너가 결정합니다.
실행마다 반복되는 지침은 [AGENTS.md](AGENTS.md), 재개는 [짧은 시작 프롬프트](docs/start.md)를 사용하세요.
코드 변경만으로 기존 예약이나 실행 중인 다른 Work가 중지되지는 않습니다.

- [제품 범위](docs/product.md) · [운영·기술 근거](docs/engineering.md)
- [donor 감사](docs/donor.md) · [현재 작업과 다음 단계](docs/current.md)
