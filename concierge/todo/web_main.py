from __future__ import annotations

import uvicorn

from concierge.todo.infrastructure.web.app import create_app

app = create_app()


def main() -> None:
    uvicorn.run("concierge.todo.web_main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
