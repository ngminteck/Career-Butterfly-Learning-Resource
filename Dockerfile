FROM python:3.10
WORKDIR /Learning-Resource
COPY ./Learning-Resource ./Learning-Resource
COPY ./requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_md


CMD ["python3","Learning-Resource.py"]