#FROM python:3.7-slim

# pinned to this version so we can use python3.7
# there are no wheels for pystan in python 3.8 which
# causes dreadfully long build times
# it is not advised to use `latest` at this time.
FROM jjanzic/docker-python3-opencv:opencv-4.0.1

COPY . /app
WORKDIR /app
RUN apt update && apt install -y libsm6 libxext6
RUN apt-get -y install tesseract-ocr
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
EXPOSE 8080
ENTRYPOINT [ "waitress-serve" ]
CMD [ "--call", "shipt:create_app" ]
