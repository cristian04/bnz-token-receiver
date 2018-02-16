FROM python:2.7

RUN mkdir /root/.minikube
RUN mkdir /root/.kube

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD python server.py
