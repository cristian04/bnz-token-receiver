FROM python:2.7-onbuild

RUN apt-get update && apt-get upgrade -y

RUN mkdir /root/.minikube
RUN mkdir /root/.kube

CMD python server.py

	
