# Windows CUDA 런타임 검증 · 2026-09-29

PR70이 병합된 main 08b0844371973883137ff83488987376cbc6383b에서 독립적으로 검증했다. PC방 Windows 10 22H2, i5-12400F, RAM 32GB, RTX 3070 8GB를 사용했다. 이 결과는 본인 PC의 최적화나 자막 품질 승인으로 쓰지 않는다. [구조화된 결과](evidence/windows-cuda-runtime.json).

## 발견과 수정

기존 설치기로 Torch 2.8.0+cu126와 저장소 의존성을 작업 폴더의 .venv에 설치했다. 70개 wheel 다운로드와 오프라인 설치, 지정 패키지 20개 및 pip check는 통과했지만 마지막 격리 진단이 60초에 걸려 설치기 전체는 401.773초, exit 1, install_existing_environment_invalid로 종료됐다.

실제 대기 스택은 NumPy 확장 초기화였다. 같은 환경에서 Torch/CUDA/Transformers를 직접 불러오면 5.453초에 완료됐다. 부모 수명 감시의 blocking stdin read와 NumPy import를 함께 실행하면 멈췄고, 입력 복제와 Win32 blocking ReadFile에서도 재현됐다. 비차단 파이프 감시는 통과했다. [NumPy의 같은 증상 보고](https://github.com/numpy/numpy/issues/24290)와 부합하지만 모든 Windows 환경에서 같은 원인이라고 주장하지 않는다.

Windows 진단 프로세스만 Python 3.12의 [비차단 파이프](https://docs.python.org/3.12/library/os.html#os.set_blocking)로 부모 연결을 50ms 간격으로 확인한다. EOF·예상하지 않은 입력·감시 실패 시 종료한다. POSIX blocking 경로, 출력 차단, 네트워크 차단, 작업자 잠금과 60초 상한은 유지한다. 모델 로딩 전에 감시를 해제하거나 GPU/의존성 기본값을 바꾸지 않았다.

## 실행한 검증

- 수정 전 실제 NumPy 회귀 검사: 10초 timeout 재현. 강제 종료 직후 임시 worker.lock 정리도 WinError32를 기록했다. 원래 실패 로그를 보존했다.
- 수정 후 전체 Python 검사: 367개 중 358개 통과, 9개 플랫폼/선택 런타임 건너뜀, 실패 0, 105.131초. 명령은 python -m unittest discover -s tests -q. 개발 환경의 NumPy 2.3.5를 사용했다.
- CUDA 환경의 test_model_check.py: 19개 통과, 2.474초. 실제 NumPy 2.5.3 import, 부모 EOF/입력 종료, 감시 설정 실패, 출력 비공개, 네트워크 차단, 시간 제한을 확인했다.
- 같은 설치 환경에서 python scripts/install_runtime.py --device cuda --data-dir <isolated-test-library> --json: 재설치 없이 기존 환경 재사용 및 CUDA ready, 6.801초, exit 0. 수정 후 새 환경 전체 다운로드·설치를 다시 실행한 결과는 아니다.
- 실제 GPU FP16 행렬곱과 scaled_dot_product_attention: 2.015초, 유한 결과 및 CPU FP32 기준과 허용 오차 비교 통과. 최대 절대 오차 각각 0.0078125 / 0.000114665. 최대 Torch 예약 메모리 22MiB. 이 작은 텐서 검사는 Qwen의 속도·VRAM 적합성을 의미하지 않는다.
- 전체 CUDA 환경으로 실제 앱을 실행하고 내장 브라우저에서 30초 720p 샘플과 가져온 한국어 자막을 재생했다. K 일시정지·J 탐색, 서버 프로세스 재시작 후 16.713147초 복원 및 자막 유지, 전체 영상 SHA256·100바이트 Range 206 응답 일치를 확인했다. 브라우저 프레임 수 계측은 제공되지 않았으며 실제 영상과 자막 화면으로 확인했다.
- 전체 설정 검사: Python·패키지·FFmpeg·ffprobe 통과. 가중치가 없어 local_models_missing, exit 1로 표시되는 것은 예상된 결과다. 설치 성공과 모델 준비 완료를 구분한다.
- 고정 코드 58a119773f2e9a196cb029959220879dac169f38를 독립 검토했다. 조치할 결함 없음. 별도 관련 검사 5개, 1.454초, exit 0. 저장소 하네스 계약 검사도 통과했다. 필수 Windows/Ubuntu CI 결과는 PR에서 별도로 확인한다.

## 다음 PC에서 이어가기

시스템 설치·드라이버·자동 시작은 변경하지 않았다. 모델 가중치·API 키·개인 영상은 받지 않았다. .venv/.venv-viewing, 설치 wheel, 샘플, 로그는 이 작업 폴더 안에 남으며 다른 PC로 가상환경을 복사하지 않는다.

본인 PC에서는 최신 소스로 설치·감상 검증을 먼저 반복한다. 이후 고정 Qwen 모델과 숨김 세션 Gemini 키를 준비하고, 실제 영상으로 생성·정렬·번역·40–120분 중단/재개 및 감상 품질을 검증한 뒤 그 기기의 처리 설정을 조정한다. 이번에는 실제 모델 추론·장편 품질·Fetch 확장 사용을 완료로 표시하지 않는다.
