FROM python:3-alpine
LABEL maintainer="Rob Svirskas <svirskasr@hhmi.org>"
COPY bin/* ./app/
WORKDIR ./app
RUN pip3 install -r requirements.txt
