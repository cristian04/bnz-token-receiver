FROM python:2.7-onbuild

RUN mkdir /root/.minikube
RUN mkdir /root/.kube

CMD python server.py