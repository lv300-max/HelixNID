FROM python:3.11-slim
WORKDIR /app
COPY HELIXNID_EMPIRICAL_LANE_ONE /app/HELIXNID_EMPIRICAL_LANE_ONE
RUN pip install --no-cache-dir -r /app/HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api/requirements.txt
EXPOSE 8000
CMD ["uvicorn", "app_v2:app", "--app-dir", "/app/HELIXNID_EMPIRICAL_LANE_ONE/product_5_6/05_api", "--host", "0.0.0.0", "--port", "8000"]
