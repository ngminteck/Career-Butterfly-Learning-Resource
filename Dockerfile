FROM python:3.10
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m spacy download en_core_web_lg

COPY . .

EXPOSE 5000

CMD ["python", "Learning-Resource.py"]
