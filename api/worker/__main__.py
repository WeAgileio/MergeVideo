"""`python -m api.worker` 入口。"""

from api.worker.runner import run_forever

if __name__ == "__main__":
    run_forever()
