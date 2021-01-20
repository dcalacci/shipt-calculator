#FROM python:3.7-slim
FROM jjanzic/docker-python3-opencv

COPY . /app
WORKDIR /app
RUN mkdir -p /root/.config/gspread
RUN mkdir -p /home/.config/gspread
COPY service_account.json /home/.config/gspread
COPY service_account.json /root/.config/gspread
RUN apt update && apt install -y libsm6 libxext6
RUN apt-get -y install tesseract-ocr
RUN pip install --upgrade pip
RUN pip install -r requirements.txt 
EXPOSE 8080 
ENTRYPOINT [ "waitress-serve" ] 
CMD [ "--call", "shipt:create_app" ] 
