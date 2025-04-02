alembic upgrade head

pytest -v functionaltests.py -p pytest_asyncio

gunicorn app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind=0.0.0.0:8000