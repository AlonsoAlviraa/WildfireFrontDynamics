# Relator Cloud Run image — scale to zero. Not the product SPA.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/hackathon PORT=8080
COPY pyproject.toml /app/pyproject.toml
COPY wildfire_front /app/wildfire_front
COPY hackathon /app/hackathon
RUN pip install --no-cache-dir numpy
EXPOSE 8080
CMD ["python", "-m", "relator.server"]
