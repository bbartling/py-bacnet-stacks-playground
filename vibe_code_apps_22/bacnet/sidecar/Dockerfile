FROM python:3.12-slim
WORKDIR /app
COPY eplus_gym /app/eplus_gym
COPY bacnet/sidecar/entrypoint.py /app/bacnet/sidecar/entrypoint.py
RUN pip install --no-cache-dir numpy gymnasium
ENV PYTHONPATH=/app
# Optional: pip install torch stable-baselines3 to load SB3 zips.
# Heuristic packs run without torch.
CMD ["python", "/app/bacnet/sidecar/entrypoint.py"]
