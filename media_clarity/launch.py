"""Open the local viewing page only after our server has bound successfully."""
import threading
import webbrowser

import uvicorn


def open_page(url):
    try:
        opened = webbrowser.open(url, new=2)
    except Exception:
        opened = False
    if not opened:
        print('브라우저를 열지 못했습니다. 위 주소를 브라우저에 직접 입력해 주세요.', flush=True)


class BrowserServer(uvicorn.Server):
    async def startup(self, sockets=None):
        await super().startup(sockets=sockets)
        if self.started:
            url = f'http://127.0.0.1:{self.config.port}'
            print(f'감상 준비가 끝났습니다: {url}\n종료하려면 이 창에서 Ctrl+C를 누르세요.', flush=True)
            # Some OS browser handlers wait for a browser process. They must not
            # hold the event loop or prevent server/worker shutdown.
            threading.Thread(target=open_page, args=(url,), daemon=True).start()
